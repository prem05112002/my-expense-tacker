import os
import re
import httpx
from pathlib import Path
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from .analytics import calculate_financial_health
from .trends import get_trends_overview, simulate_affordability
from ..schemas.trends import AffordabilitySimulation

# Load environment variables from backend/.env
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


# Rate limiting state (in-memory - resets on server restart)
_rate_limit_state = {
    "requests_today": 0,
    "last_reset": date.today(),
    "requests_per_minute": [],
}

DAILY_LIMIT = 1500
PER_MINUTE_LIMIT = 15


def _check_rate_limit() -> Tuple[bool, Dict[str, Any]]:
    """Check if we're within rate limits. Returns (allowed, status_info)."""
    today = date.today()

    # Reset daily counter if new day
    if _rate_limit_state["last_reset"] != today:
        _rate_limit_state["requests_today"] = 0
        _rate_limit_state["last_reset"] = today

    # Clean up old minute timestamps
    now = datetime.now()
    _rate_limit_state["requests_per_minute"] = [
        ts for ts in _rate_limit_state["requests_per_minute"]
        if (now - ts).total_seconds() < 60
    ]

    daily_remaining = DAILY_LIMIT - _rate_limit_state["requests_today"]
    minute_remaining = PER_MINUTE_LIMIT - len(_rate_limit_state["requests_per_minute"])

    status = {
        "daily_remaining": daily_remaining,
        "minute_remaining": minute_remaining,
        "daily_limit": DAILY_LIMIT,
        "minute_limit": PER_MINUTE_LIMIT,
    }

    if daily_remaining <= 0:
        return False, {**status, "error": "Daily limit reached. Resets at midnight."}
    if minute_remaining <= 0:
        return False, {**status, "error": "Rate limit reached. Wait a minute."}

    return True, status


def _record_llm_request():
    """Record an LLM request for rate limiting."""
    _rate_limit_state["requests_today"] += 1
    _rate_limit_state["requests_per_minute"].append(datetime.now())


def get_rate_limit_status() -> Dict[str, Any]:
    """Get current rate limit status."""
    _, status = _check_rate_limit()
    return status


# Intent Detection (Local)
def detect_intent(query: str) -> Tuple[str, Dict[str, Any]]:
    """
    Detect user intent from query. Returns (intent_type, extracted_params).
    All processing is local - no LLM call.
    """
    query_lower = query.lower()

    # Affordability patterns
    affordability_patterns = [
        r"can i (?:afford|buy|purchase|get)",
        r"should i buy",
        r"is .+ affordable",
        r"budget for",
        r"emi for",
    ]
    for pattern in affordability_patterns:
        if re.search(pattern, query_lower):
            return "affordability", {"raw_query": query}

    # Category/spending patterns
    category_patterns = [
        r"how much (?:do i|did i) spend on (.+)",
        r"spending on (.+)",
        r"(.+) expenses?",
        r"what(?:'s| is) my (.+) spend",
    ]
    for pattern in category_patterns:
        match = re.search(pattern, query_lower)
        if match:
            category = match.group(1).strip()
            # Remove trailing punctuation (?, !, ., etc.)
            category = re.sub(r"[?!.,;:]+$", "", category).strip()
            return "category_spend", {"category": category}

    # Budget status patterns
    budget_patterns = [
        r"(?:what'?s?|how'?s?) my (?:remaining )?budget",
        r"budget (?:status|left|remaining)",
        r"how much (?:can i|do i have to) spend",
        r"am i over budget",
    ]
    for pattern in budget_patterns:
        if re.search(pattern, query_lower):
            return "budget_status", {}

    # Trends patterns
    trends_patterns = [
        r"spending trend",
        r"how (?:has|have) my (?:spending|expenses) (?:changed|been)",
        r"month(?:ly)? comparison",
        r"which (?:month|day) do i spend",
    ]
    for pattern in trends_patterns:
        if re.search(pattern, query_lower):
            return "trends", {}

    # Savings advice patterns
    savings_patterns = [
        r"where can i (?:save|cut)",
        r"reduce (?:my )?(?:spending|expenses)",
        r"saving (?:tips|advice)",
        r"how (?:can i|to) save",
    ]
    for pattern in savings_patterns:
        if re.search(pattern, query_lower):
            return "savings_advice", {}

    # General/unknown
    return "general", {"raw_query": query}


async def _call_gemini_api(prompt: str, system_instruction: str = "") -> Optional[str]:
    """
    Call Gemini API for LLM tasks.
    Only sends non-financial data (product names, formatting requests).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    allowed, status = _check_rate_limit()
    if not allowed:
        return f"Rate limit exceeded: {status.get('error', 'Try again later.')}"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 500,
        }
    }

    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            _record_llm_request()

            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return None
    except httpx.HTTPStatusError as e:
        # Include response body for debugging
        try:
            error_detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            error_detail = e.response.text[:200] if e.response.text else ""
        return f"API error: {e.response.status_code} - {error_detail}"
    except Exception as e:
        return f"Error calling LLM: {str(e)}"


async def _extract_product_price(product_query: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """
    Use LLM to extract product name and estimated price.
    Only the product name is sent to LLM, not financial data.
    Returns (product, price, error_message).
    """
    prompt = f"""Extract the product name and estimate its price in INR from this query: "{product_query}"

Return ONLY in this exact format (no other text):
Product: [product name]
Price: [estimated monthly cost or EMI in INR as a number]

If it's a one-time purchase, estimate a reasonable EMI (12-month).
If you cannot determine the product or price, return:
Product: unknown
Price: 0"""

    response = await _call_gemini_api(prompt)
    if not response:
        return None, None, "No response from LLM. Check if GEMINI_API_KEY is configured in backend/.env"

    # Check if response is an error message from the API
    error_prefixes = ["API error:", "Error calling LLM:", "Rate limit exceeded:"]
    for prefix in error_prefixes:
        if response.startswith(prefix):
            return None, None, response

    product = None
    price = None

    # More robust parsing - handle various response formats
    response_text = response.strip()

    # Try line-by-line parsing first
    for line in response_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        line_lower = line.lower()

        # Match product line (handle variations like "Product:", "**Product:**", etc.)
        if "product" in line_lower and ":" in line:
            # Extract everything after the first colon
            product_part = line.split(":", 1)[1].strip()
            # Remove markdown formatting if present
            product_part = re.sub(r"[\*\#\_\`]", "", product_part).strip()
            if product_part and product_part.lower() != "unknown":
                product = product_part

        # Match price line
        elif "price" in line_lower and ":" in line:
            try:
                price_part = line.split(":", 1)[1].strip()
                # Remove currency symbols, commas, and extract number
                price_str = re.sub(r"[₹$,\s]", "", price_part)
                # Find first number in the string
                match = re.search(r"[\d.]+", price_str)
                if match:
                    price = float(match.group())
            except (ValueError, IndexError):
                price = None

    # Fallback: try regex patterns on full response if line parsing failed
    if not product:
        product_match = re.search(r"product[:\s]+([^\n₹$\d]+)", response_text, re.IGNORECASE)
        if product_match:
            product = product_match.group(1).strip()
            product = re.sub(r"[\*\#\_\`]", "", product).strip()

    if not price:
        # Look for any number preceded by ₹ or followed by INR/rupees
        price_match = re.search(r"₹?\s*([\d,]+(?:\.\d+)?)\s*(?:INR|rupees?)?", response_text, re.IGNORECASE)
        if price_match:
            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                price = None

    return product, price, None


async def _format_response_with_llm(data: Dict[str, Any], user_query: str) -> str:
    """
    Use LLM to format a natural language response.
    Financial data is pre-computed locally and only summary is sent.
    """
    prompt = f"""User asked: "{user_query}"

Here is the computed financial summary (no raw transaction data):
{data}

Write a helpful, concise response (2-3 sentences max) answering their question.
Be friendly but direct. Use currency symbol ₹ for amounts."""

    response = await _call_gemini_api(
        prompt,
        system_instruction="You are a helpful financial assistant. Keep responses brief and actionable."
    )
    return response or str(data)


# Intent Handlers (All compute locally, only use LLM for formatting)

async def handle_budget_status(db: AsyncSession) -> str:
    """Handle budget status query - all local computation."""
    try:
        health = await calculate_financial_health(db, offset=0)

        return (
            f"Your current budget status:\n"
            f"- Budget: ₹{health['total_budget']:,.2f}\n"
            f"- Spent: ₹{health['total_spend']:,.2f}\n"
            f"- Remaining: ₹{health['budget_remaining']:,.2f}\n"
            f"- Days left: {health['days_left']}\n"
            f"- Safe to spend daily: ₹{health['safe_to_spend_daily']:,.2f}\n"
            f"- Status: {health['burn_rate_status']}"
        )
    except Exception as e:
        return f"Unable to fetch budget status. Please try again later. (Error: {str(e)})"


async def handle_category_spend(db: AsyncSession, category: str) -> str:
    """Handle category spending query - local lookup."""
    try:
        health = await calculate_financial_health(db, offset=0)

        # Find matching category (fuzzy)
        categories = health.get("category_breakdown", [])
        matched = None
        for cat in categories:
            if category.lower() in cat["name"].lower():
                matched = cat
                break

        if matched:
            return (
                f"Your spending on {matched['name']} this cycle: ₹{matched['value']:,.2f}"
            )
        else:
            cat_list = ", ".join([c["name"] for c in categories[:5]])
            return f"No category matching '{category}' found. Your top categories: {cat_list}"
    except Exception as e:
        return f"Unable to fetch category spending. Please try again later. (Error: {str(e)})"


async def handle_trends(db: AsyncSession) -> str:
    """Handle trends query - local computation."""
    try:
        trends = await get_trends_overview(db)

        if not trends.category_trends:
            return "Not enough data to analyze trends yet."

        # Build summary locally
        increasing = [c.category for c in trends.category_trends if c.trend == "increasing"][:3]
        decreasing = [c.category for c in trends.category_trends if c.trend == "decreasing"][:3]

        high_spend_months = [p.month_name for p in trends.seasonal_patterns if p.is_high_spend]

        response = "Spending trends analysis:\n"
        if increasing:
            response += f"- Increasing: {', '.join(increasing)}\n"
        if decreasing:
            response += f"- Decreasing: {', '.join(decreasing)}\n"
        if high_spend_months:
            response += f"- High-spend months: {', '.join(high_spend_months)}\n"

        if trends.recurring_patterns:
            top_recurring = trends.recurring_patterns[0]
            response += f"- Top recurring: {top_recurring.merchant_name} ({top_recurring.frequency})"

        return response
    except Exception as e:
        return f"Unable to fetch spending trends. Please try again later. (Error: {str(e)})"


async def handle_savings_advice(db: AsyncSession) -> str:
    """Handle savings advice query - local analysis."""
    try:
        health = await calculate_financial_health(db, offset=0)
        trends = await get_trends_overview(db)

        advice = ["Here are some savings suggestions:"]

        # Find increasing categories
        increasing = [c for c in trends.category_trends if c.trend == "increasing"]
        if increasing:
            top = increasing[0]
            advice.append(
                f"- {top.category} spending increased {top.change_percent:.0f}% - consider reviewing"
            )

        # Find high-value categories
        categories = health.get("category_breakdown", [])
        if categories:
            top_cat = categories[0]
            advice.append(f"- Your biggest expense: {top_cat['name']} (₹{top_cat['value']:,.0f})")

        # Check burn rate
        if health["burn_rate_status"] in ["High Burn", "Caution"]:
            advice.append(f"- Current status: {health['burn_rate_status']} - slow down spending")

        return "\n".join(advice)
    except Exception as e:
        return f"Unable to generate savings advice. Please try again later. (Error: {str(e)})"


async def handle_affordability(db: AsyncSession, raw_query: str) -> str:
    """
    Handle affordability query.
    Uses LLM only to extract product/price, then local computation.
    """
    try:
        product, price, error = await _extract_product_price(raw_query)

        # If there was an API error, show it to the user
        if error:
            return f"Unable to check affordability: {error}"

        if not product or not price or price <= 0:
            return (
                "I couldn't determine the product price. "
                "Try: 'Can I afford a ₹5000 monthly EMI?' with a specific amount."
            )

        # Local affordability calculation
        simulation = AffordabilitySimulation(monthly_expense=price)
        result = await simulate_affordability(db, simulation)

        status = "Yes" if result.can_afford else "No"
        return (
            f"Can you afford {product}?\n"
            f"- Answer: {status}\n"
            f"- Estimated monthly cost: ₹{price:,.0f}\n"
            f"- Your budget: ₹{result.current_budget:,.0f}\n"
            f"- Current avg spend: ₹{result.current_avg_spend:,.0f}\n"
            f"- With new expense: ₹{result.projected_spend_with_new:,.0f}\n"
            f"- Budget impact: {result.impact_percent:.1f}%\n"
            f"- {result.recommendation}"
        )
    except Exception as e:
        return f"Unable to check affordability. Please try again later. (Error: {str(e)})"


async def handle_general(db: AsyncSession, raw_query: str) -> str:
    """Handle general queries by providing available commands."""
    return (
        "I can help you with:\n"
        "- 'What's my budget status?' - Check remaining budget\n"
        "- 'How much do I spend on food?' - Category breakdown\n"
        "- 'What are my spending trends?' - Trend analysis\n"
        "- 'Can I afford an iPhone 15?' - Affordability check\n"
        "- 'Where can I save money?' - Savings suggestions\n\n"
        "Try asking one of these!"
    )


async def process_chat_message(db: AsyncSession, message: str) -> Dict[str, Any]:
    """
    Main entry point for chat messages.
    Returns response with intent detection and appropriate handling.
    """
    intent, params = detect_intent(message)

    handlers = {
        "budget_status": lambda: handle_budget_status(db),
        "category_spend": lambda: handle_category_spend(db, params.get("category", "")),
        "trends": lambda: handle_trends(db),
        "savings_advice": lambda: handle_savings_advice(db),
        "affordability": lambda: handle_affordability(db, params.get("raw_query", message)),
        "general": lambda: handle_general(db, params.get("raw_query", message)),
    }

    handler = handlers.get(intent, handlers["general"])
    response = await handler()

    return {
        "response": response,
        "intent": intent,
        "requires_llm": intent == "affordability",
        "rate_limit": get_rate_limit_status(),
    }
