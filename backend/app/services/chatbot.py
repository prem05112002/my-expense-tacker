import json
import os
import re
import httpx
import uuid
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dotenv import load_dotenv
from .analytics import calculate_financial_health
from .trends import get_trends_overview, simulate_affordability
from . import chatbot_compute
from ..schemas.trends import AffordabilitySimulation
from ..schemas.chatbot import (
    OperationType, Operation, QueryPlan, OperationResult,
    ChatQueryParams, TimeRange, SpendingAdjustment, ChatMessage,
    get_query_plan_schema_v2, get_multi_operation_schema
)
from .. import models

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


# ============================================
# Session Management
# ============================================

class ConversationSession:
    """Stores conversation state for multi-turn interactions."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[Dict[str, Any]] = []  # Last N messages
        self.last_query_params: Optional[ChatQueryParams] = None
        self.last_results: Optional[Dict[str, Any]] = None
        self.last_accessed: float = time.time()

    def add_message(self, role: str, content: str, params: Optional[ChatQueryParams] = None):
        """Add a message to the conversation history."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "params": params.model_dump() if params else None,
        })
        # Keep only last 10 messages
        if len(self.messages) > 10:
            self.messages = self.messages[-10:]
        self.last_accessed = time.time()

    def get_history_for_llm(self) -> str:
        """Format conversation history for LLM context."""
        if not self.messages:
            return "No previous conversation."

        history_lines = []
        for msg in self.messages[-6:]:  # Last 6 messages for context
            role = "User" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")

        return "\n".join(history_lines)


class SessionManager:
    """Manages conversation sessions with TTL and cleanup."""

    TTL_SECONDS = 30 * 60  # 30 minutes
    MAX_SESSIONS = 1000

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create_session(self, session_id: Optional[str] = None) -> ConversationSession:
        """Get existing session or create a new one."""
        self._maybe_cleanup()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            session.last_accessed = time.time()
            return session

        # Create new session
        new_id = session_id or str(uuid.uuid4())
        session = ConversationSession(new_id)
        self._sessions[new_id] = session
        return session

    def _maybe_cleanup(self):
        """Remove expired sessions."""
        now = time.time()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.last_accessed > self.TTL_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]

        # If still over limit, remove oldest
        if len(self._sessions) > self.MAX_SESSIONS:
            sorted_sessions = sorted(
                self._sessions.items(),
                key=lambda x: x[1].last_accessed
            )
            for sid, _ in sorted_sessions[:len(self._sessions) - self.MAX_SESSIONS]:
                del self._sessions[sid]


# Global session manager instance
_session_manager = SessionManager()


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

    # Time range spending patterns (new)
    time_range_patterns = [
        r"(?:how much|what) (?:have i|did i) spend (?:on )?(.+?)(?:in|during|over|for) (?:the )?(?:past|last) (\d+) months?",
        r"(.+?) (?:spending|expenses?) (?:in|during|over|for) (?:the )?(?:past|last) (\d+) months?",
        r"(?:how much|what) (?:have i|did i) spend (?:on )?(.+?) (?:last|this) (?:week|month)",
        r"(.+?) (?:spending|expenses?) (?:last|this) (?:week|month)",
    ]
    for pattern in time_range_patterns:
        match = re.search(pattern, query_lower)
        if match:
            category = match.group(1).strip()
            category = re.sub(r"[?!.,;:]+$", "", category).strip()
            months = int(match.group(2)) if len(match.groups()) > 1 and match.group(2) else 1
            return "time_range_spend", {"category": category, "months_back": months}

    # Goal planning patterns (new)
    goal_patterns = [
        r"(?:can i|how (?:can i|do i|to)) save (?:₹)?(\d[\d,]*)(?: ?k)? (?:in|within|by) (\d+) months?",
        r"save (?:₹)?(\d[\d,]*)(?: ?k)? (?:in|within|by) (\d+) months?",
        r"(?:want to|need to|planning to) save (?:₹)?(\d[\d,]*)",
    ]
    for pattern in goal_patterns:
        match = re.search(pattern, query_lower)
        if match:
            amount_str = match.group(1).replace(",", "")
            amount = float(amount_str)
            if "k" in query_lower[match.start():match.end()+2]:
                amount *= 1000
            months = int(match.group(2)) if len(match.groups()) > 1 else None
            return "goal_planning", {"target_amount": amount, "target_months": months}

    # Budget forecast patterns (new)
    forecast_patterns = [
        r"will i (?:stay|be|remain) (?:under|within) budget",
        r"am i going to (?:overspend|exceed|go over)",
        r"(?:end of )?(?:month|cycle) (?:budget )?(?:forecast|projection)",
        r"(?:predict|project) (?:my )?(?:spending|budget)",
    ]
    for pattern in forecast_patterns:
        if re.search(pattern, query_lower):
            return "budget_forecast", {}

    # Average spending patterns (new)
    avg_patterns = [
        r"(?:what'?s?|what is) (?:my )?average (?:monthly )?(.+?) spend",
        r"average (?:monthly )?(?:spending|expenses?) (?:on|for) (.+)",
        r"how much do i (?:usually|typically|normally) spend on (.+)",
    ]
    for pattern in avg_patterns:
        match = re.search(pattern, query_lower)
        if match:
            category = match.group(1).strip()
            category = re.sub(r"[?!.,;:]+$", "", category).strip()
            return "average_spending", {"category": category}

    # Spending velocity patterns (new)
    velocity_patterns = [
        r"(?:am i|is my) spending (?:increasing|decreasing|going up|going down)",
        r"spending (?:rate|velocity|pace)",
        r"(?:how )?(?:fast|quickly) am i spending",
    ]
    for pattern in velocity_patterns:
        if re.search(pattern, query_lower):
            return "spending_velocity", {}

    # General/unknown
    return "general", {"raw_query": query}


def _get_query_plan_schema() -> Dict[str, Any]:
    """Return JSON schema for QueryPlan to enforce structured output from Gemini."""
    return {
        "type": "object",
        "properties": {
            "query_summary": {"type": "string"},
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "budget_status", "category_spend", "trends_overview",
                                "affordability_check", "savings_advice", "custom_scenario",
                                "clarify", "future_projection", "goal_planning",
                                "budget_forecast", "time_range_spend", "average_spending",
                                "spending_velocity"
                            ]
                        },
                        "params": {"type": "object"},
                        "description": {"type": "string"}
                    },
                    "required": ["type", "params", "description"]
                }
            },
            "requires_clarification": {"type": "boolean"},
            "clarification_question": {"type": ["string", "null"]}
        },
        "required": ["query_summary", "operations", "requires_clarification"]
    }


async def _call_gemini_api(
    prompt: str,
    system_instruction: str = "",
    response_schema: Optional[Dict[str, Any]] = None,
    temperature: float = 0.7
) -> Optional[str]:
    """
    Call Gemini API for LLM tasks.
    Only sends non-financial data (product names, formatting requests).

    Args:
        prompt: The prompt to send to the model
        system_instruction: Optional system instruction for the model
        response_schema: Optional JSON schema to enforce structured output
        temperature: Model temperature (0 = deterministic, 1 = creative)
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    allowed, status = _check_rate_limit()
    if not allowed:
        return f"Rate limit exceeded: {status.get('error', 'Try again later.')}"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    generation_config = {
        "temperature": temperature,
        "maxOutputTokens": 2048,
    }

    # Enable JSON mode if schema is provided
    if response_schema:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = response_schema

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": generation_config
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
        system_instruction="You are a helpful financial assistant. Keep responses brief and actionable.",
        temperature=0.5  # Allow some creativity for natural responses
    )
    return response  # Return None if no response, let handlers use fallback


def _is_valid_llm_response(response: Optional[str]) -> bool:
    """Check if LLM response is valid and usable."""
    if not response:
        return False
    # Check for error prefixes
    error_prefixes = ("API error:", "Error calling LLM:", "Rate limit exceeded:")
    if response.startswith(error_prefixes):
        return False
    # Check for dict string representation (indicates fallback failure)
    if response.startswith("{") and response.endswith("}"):
        return False
    return True


# ============================================
# Conversational Query Processing (LLM-based)
# ============================================

async def _get_categories(db: AsyncSession) -> List[str]:
    """Fetch all category names from the database."""
    stmt = select(models.Category.name)
    result = await db.execute(stmt)
    return [row[0] for row in result.fetchall()]


async def _get_financial_context(db: AsyncSession) -> Dict[str, Any]:
    """Get aggregated financial context (no raw transaction data)."""
    try:
        health = await calculate_financial_health(db, offset=0)
        return {
            "budget": health.get("total_budget", 0),
            "spent": health.get("total_spend", 0),
            "remaining": health.get("budget_remaining", 0),
            "days_left": health.get("days_left", 0),
            "status": health.get("burn_rate_status", "Unknown"),
            "top_categories": [c["name"] for c in health.get("category_breakdown", [])[:5]],
        }
    except Exception:
        return {"budget": 0, "spent": 0, "remaining": 0, "days_left": 0, "status": "Unknown", "top_categories": []}


async def _get_historical_averages(db: AsyncSession, months_back: int = 3) -> Dict[str, Any]:
    """
    Calculate historical monthly averages for budget planning and projections.
    Returns average monthly income, spend, spend by category, and monthly surplus.
    """
    from .rules import get_or_create_settings
    from collections import defaultdict

    settings = await get_or_create_settings(db)
    ignored_cats = [x.strip() for x in settings.ignored_categories.split(',')] if settings.ignored_categories else []
    income_cats = [x.strip() for x in settings.income_categories.split(',')] if settings.income_categories else []

    # Fetch transactions for the period
    cutoff_date = date.today() - timedelta(days=months_back * 30)
    stmt = (
        select(
            models.Transaction.amount,
            models.Transaction.txn_date,
            models.Transaction.payment_type,
            models.Category.name.label("category_name")
        )
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.txn_date >= cutoff_date)
    )
    result = await db.execute(stmt)
    transactions = result.mappings().all()

    # Aggregate by month
    monthly_income = defaultdict(float)
    monthly_spend = defaultdict(float)
    monthly_category_spend = defaultdict(lambda: defaultdict(float))

    for txn in transactions:
        month_key = f"{txn.txn_date.year}-{txn.txn_date.month:02d}"
        p_type = (txn.payment_type or "").upper()
        amount = float(txn.amount)
        cat_name = txn.category_name

        if cat_name in ignored_cats:
            continue

        if cat_name in income_cats:
            if p_type == "CREDIT":
                monthly_income[month_key] += amount
        else:
            if p_type == "DEBIT":
                monthly_spend[month_key] += amount
                monthly_category_spend[month_key][cat_name] += amount

    # Calculate averages
    num_months = len(monthly_spend) if monthly_spend else 1

    avg_monthly_income = sum(monthly_income.values()) / max(len(monthly_income), 1)
    avg_monthly_spend = sum(monthly_spend.values()) / num_months

    # Average spend by category
    category_totals = defaultdict(float)
    for month_data in monthly_category_spend.values():
        for cat, amount in month_data.items():
            category_totals[cat] += amount

    avg_category_spend = {cat: total / num_months for cat, total in category_totals.items()}

    # Calculate budget based on settings
    if settings.budget_type == "PERCENTAGE" and avg_monthly_income > 0:
        avg_budget = (avg_monthly_income * settings.budget_value) / 100
    else:
        avg_budget = float(settings.budget_value)

    avg_monthly_surplus = avg_budget - avg_monthly_spend

    return {
        "avg_monthly_income": round(avg_monthly_income, 2),
        "avg_monthly_spend": round(avg_monthly_spend, 2),
        "avg_monthly_budget": round(avg_budget, 2),
        "avg_monthly_surplus": round(avg_monthly_surplus, 2),
        "avg_category_spend": {k: round(v, 2) for k, v in avg_category_spend.items()},
        "months_of_data": num_months,
        "budget_type": settings.budget_type,
    }


def _check_rate_limit_for_conversation() -> Tuple[bool, str]:
    """
    Check if we have enough rate limit quota for a full conversation flow.
    Conversation flow uses 2 LLM calls: analyze + format.
    """
    allowed, status = _check_rate_limit()
    if not allowed:
        return False, status.get("error", "Rate limit exceeded")

    # Need at least 2 requests for full flow
    if status.get("minute_remaining", 0) < 2:
        return False, "Insufficient rate limit quota for conversation. Wait a moment."
    if status.get("daily_remaining", 0) < 2:
        return False, "Daily limit almost reached. Using simplified response."

    return True, ""


async def _analyze_query_with_llm(db: AsyncSession, user_query: str) -> Optional[QueryPlan]:
    """
    Use LLM to parse natural language query into structured operations.
    Returns QueryPlan with operations to execute, or None if analysis fails.

    Uses Gemini's structured output mode (responseSchema) to guarantee valid JSON.
    """
    # Get context for the LLM
    categories = await _get_categories(db)
    context = await _get_financial_context(db)
    historical = await _get_historical_averages(db, months_back=3)

    # Format category spend for context
    top_cat_spend = sorted(historical['avg_category_spend'].items(), key=lambda x: x[1], reverse=True)[:5]
    cat_spend_str = ", ".join([f"{cat}: ₹{amt:,.0f}" for cat, amt in top_cat_spend])

    prompt = f"""You are a financial assistant. Parse the user's question into operations to execute.

Available operations:
1. budget_status - Get current budget, spending, and remaining amount
2. category_spend (params: category_name) - Get spending for a specific category
3. trends_overview - Get spending trends analysis
4. affordability_check (params: product_name, monthly_cost) - Check if user can afford something
   - The system will automatically look up the price if monthly_cost=0
   - This compares against projected savings from previous operations
5. savings_advice - Get savings suggestions
6. custom_scenario (params: adjustments, months) - Project future savings with spending changes
   - adjustments: dict of category name to monthly change (e.g., {{"Food": -10000}} means reduce food by 10k/month)
   - months: number of months to project forward
   - This calculates: (avg_budget - (avg_spend - reductions)) * months = total_projected_savings

User's categories: {', '.join(categories) if categories else 'Unknown'}

HISTORICAL AVERAGES (past 3 months - USE THESE FOR PROJECTIONS):
- Average monthly budget: ₹{historical['avg_monthly_budget']:,.0f}
- Average monthly spend: ₹{historical['avg_monthly_spend']:,.0f}
- Average monthly surplus (budget - spend): ₹{historical['avg_monthly_surplus']:,.0f}
- Average spend by top categories: {cat_spend_str}

Current cycle: Budget ₹{context['budget']:,.0f}, Spent ₹{context['spent']:,.0f}, Days left: {context['days_left']}

EXAMPLE - Complex predictive query:
Input: "Can I afford Japan flights if I reduce food by 10k for 6 months?"
Output:
{{"query_summary": "Check if reducing food spending enables affording Japan flights", "operations": [{{"type": "custom_scenario", "params": {{"adjustments": {{"Food": -10000}}, "months": 6}}, "description": "Project savings from reducing food by 10k/month for 6 months"}}, {{"type": "affordability_check", "params": {{"product_name": "Japan flight tickets", "monthly_cost": 0}}, "description": "Check if projected savings cover flight cost"}}], "requires_clarification": false, "clarification_question": null}}

EXAMPLE - Simple budget query:
Input: "What's my budget?"
Output:
{{"query_summary": "Check current budget status", "operations": [{{"type": "budget_status", "params": {{}}, "description": "Get current budget, spending, and remaining amount"}}], "requires_clarification": false, "clarification_question": null}}

IMPORTANT RULES:
- For predictive/future queries with spending changes, ALWAYS use custom_scenario FIRST, then affordability_check
- DO NOT ask for clarification if you can calculate it - use the historical averages provided
- For flight/travel/product costs, set monthly_cost=0 and the system will look up the price
- Never set requires_clarification=true if the query can be answered with the available data

User query: "{user_query}" """

    response = await _call_gemini_api(
        prompt,
        system_instruction="You are a financial query analyzer. Output valid JSON only.",
        response_schema=_get_query_plan_schema(),
        temperature=0  # Deterministic for structured output
    )

    if not response or not _is_valid_llm_response(response):
        return None

    try:
        # Clean up response - remove markdown code blocks if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # Remove markdown code block
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        data = json.loads(cleaned)

        # Parse operations
        operations = []
        for op_data in data.get("operations", []):
            try:
                op_type = OperationType(op_data.get("type", "clarify"))
                operations.append(Operation(
                    type=op_type,
                    params=op_data.get("params", {}),
                    description=op_data.get("description", "")
                ))
            except ValueError:
                # Invalid operation type, skip
                continue

        if not operations:
            return None

        return QueryPlan(
            operations=operations,
            requires_clarification=data.get("requires_clarification", False),
            clarification_question=data.get("clarification_question"),
            query_summary=data.get("query_summary", user_query)
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


async def _execute_custom_scenario(
    db: AsyncSession,
    params: Dict[str, Any],
    accumulated_context: Dict[str, Any]
) -> OperationResult:
    """
    Execute a custom hypothetical scenario calculation using HISTORICAL AVERAGES.

    This calculates:
    - Current avg monthly surplus = avg_budget - avg_spend
    - Adjustment savings = sum of spending reductions
    - New monthly surplus = current_surplus + adjustment_savings
    - Total projected savings = new_monthly_surplus * months

    Params:
    - adjustments: Dict of category -> monthly change (e.g., {"Food": -10000})
    - months: Number of months to project
    """
    try:
        # Use historical averages for accurate projections
        historical = await _get_historical_averages(db, months_back=3)

        adjustments = params.get("adjustments", {})
        months = params.get("months", 6)

        avg_budget = historical["avg_monthly_budget"]
        avg_spend = historical["avg_monthly_spend"]
        avg_category_spend = historical["avg_category_spend"]
        current_monthly_surplus = historical["avg_monthly_surplus"]

        # Calculate additional savings from adjustments
        additional_monthly_savings = 0.0
        adjustment_details = {}

        for cat_name, change in adjustments.items():
            # Find matching category (fuzzy match)
            matched_cat = None
            matched_current_spend = 0

            for existing_cat, spend in avg_category_spend.items():
                if cat_name.lower() in existing_cat.lower() or existing_cat.lower() in cat_name.lower():
                    matched_cat = existing_cat
                    matched_current_spend = spend
                    break

            if matched_cat:
                # change is negative for reductions (e.g., -10000)
                # Savings = min(reduction amount, current spend) to avoid negative spend
                reduction = abs(change) if change < 0 else 0
                actual_savings = min(reduction, matched_current_spend)
                additional_monthly_savings += actual_savings
                adjustment_details[matched_cat] = {
                    "current_avg_spend": matched_current_spend,
                    "reduction": actual_savings,
                    "new_avg_spend": matched_current_spend - actual_savings
                }
            else:
                # Category not found, still count the intended reduction
                reduction = abs(change) if change < 0 else 0
                additional_monthly_savings += reduction
                adjustment_details[cat_name] = {
                    "current_avg_spend": 0,
                    "reduction": reduction,
                    "new_avg_spend": 0,
                    "note": "Category not found in historical data"
                }

        # Calculate new monthly surplus with adjustments
        new_monthly_surplus = current_monthly_surplus + additional_monthly_savings

        # Project total savings over the period
        total_projected_savings = new_monthly_surplus * months

        result_data = {
            "adjustments_applied": adjustments,
            "adjustment_details": adjustment_details,
            "avg_monthly_budget": avg_budget,
            "avg_monthly_spend": avg_spend,
            "current_monthly_surplus": current_monthly_surplus,
            "additional_monthly_savings": additional_monthly_savings,
            "new_monthly_surplus": new_monthly_surplus,
            "months_projected": months,
            "total_projected_savings": total_projected_savings,
            "months_of_historical_data": historical["months_of_data"],
        }

        # Store in accumulated context for chained operations (affordability check)
        accumulated_context["scenario_savings"] = total_projected_savings
        accumulated_context["monthly_surplus"] = new_monthly_surplus
        accumulated_context["historical"] = historical

        return OperationResult(
            operation_type=OperationType.CUSTOM_SCENARIO,
            success=True,
            data=result_data
        )
    except Exception as e:
        return OperationResult(
            operation_type=OperationType.CUSTOM_SCENARIO,
            success=False,
            error=str(e)
        )


async def _execute_operations(
    db: AsyncSession,
    operations: List[Operation]
) -> List[OperationResult]:
    """
    Execute a list of operations and return results.
    Operations can be chained - results from earlier ops inform later ones.
    """
    results = []
    accumulated_context = {}  # Shared context between operations

    for op in operations:
        try:
            if op.type == OperationType.BUDGET_STATUS:
                health = await calculate_financial_health(db, offset=0)
                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data={
                        "budget": health["total_budget"],
                        "spent": health["total_spend"],
                        "remaining": health["budget_remaining"],
                        "days_left": health["days_left"],
                        "safe_daily": health["safe_to_spend_daily"],
                        "status": health["burn_rate_status"],
                    }
                ))
                accumulated_context["health"] = health

            elif op.type == OperationType.CATEGORY_SPEND:
                health = accumulated_context.get("health") or await calculate_financial_health(db, offset=0)
                category_name = op.params.get("category_name", "")
                categories = health.get("category_breakdown", [])

                matched = None
                for cat in categories:
                    if category_name.lower() in cat["name"].lower():
                        matched = cat
                        break

                if matched:
                    results.append(OperationResult(
                        operation_type=op.type,
                        success=True,
                        data={
                            "category": matched["name"],
                            "amount": matched["value"],
                            "percentage": (matched["value"] / health["total_spend"] * 100) if health["total_spend"] > 0 else 0,
                        }
                    ))
                else:
                    results.append(OperationResult(
                        operation_type=op.type,
                        success=True,
                        data={
                            "category": category_name,
                            "amount": 0,
                            "not_found": True,
                            "available_categories": [c["name"] for c in categories[:5]],
                        }
                    ))

            elif op.type == OperationType.TRENDS_OVERVIEW:
                trends = await get_trends_overview(db)
                increasing = [c.category for c in trends.category_trends if c.trend == "increasing"][:3]
                decreasing = [c.category for c in trends.category_trends if c.trend == "decreasing"][:3]
                high_spend_months = [p.month_name for p in trends.seasonal_patterns if p.is_high_spend]

                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data={
                        "increasing_categories": increasing,
                        "decreasing_categories": decreasing,
                        "high_spend_months": high_spend_months,
                        "top_recurring": trends.recurring_patterns[0].merchant_name if trends.recurring_patterns else None,
                    }
                ))
                accumulated_context["trends"] = trends

            elif op.type == OperationType.AFFORDABILITY_CHECK:
                product_name = op.params.get("product_name", "")
                monthly_cost = op.params.get("monthly_cost", 0)

                # Get scenario context from previous operations
                scenario_savings = accumulated_context.get("scenario_savings", 0)
                monthly_surplus = accumulated_context.get("monthly_surplus", 0)
                historical = accumulated_context.get("historical")

                # If monthly_cost is 0, get price from LLM
                # For one-time purchases (flights, etc.), we get total price
                product_price = 0
                is_one_time_purchase = False

                if monthly_cost <= 0 and product_name:
                    # Ask LLM for price - specify we want total cost for one-time items
                    price_prompt = f"""What is the estimated price in INR for: "{product_name}"

For one-time purchases (flights, electronics, etc.), give the TOTAL price.
For subscriptions/recurring expenses, give the MONTHLY cost.

Return ONLY in this format:
Product: [name]
Price: [number in INR]
Type: [one-time or monthly]"""

                    price_response = await _call_gemini_api(price_prompt)
                    if price_response and _is_valid_llm_response(price_response):
                        # Parse the response
                        for line in price_response.split("\n"):
                            line_lower = line.lower()
                            if "price" in line_lower and ":" in line:
                                try:
                                    price_str = re.sub(r"[₹$,\s]", "", line.split(":", 1)[1])
                                    match = re.search(r"[\d.]+", price_str)
                                    if match:
                                        product_price = float(match.group())
                                except (ValueError, IndexError):
                                    pass
                            elif "type" in line_lower and ":" in line:
                                type_str = line.split(":", 1)[1].strip().lower()
                                is_one_time_purchase = "one" in type_str or "total" in type_str
                else:
                    product_price = monthly_cost

                if product_price > 0:
                    # Determine affordability based on context
                    if scenario_savings > 0:
                        # We have projected savings from a custom_scenario
                        if is_one_time_purchase:
                            # Compare total savings against total price
                            can_afford = scenario_savings >= product_price
                            affordability_details = {
                                "comparison": "projected_savings vs total_price",
                                "projected_savings": scenario_savings,
                                "product_total_price": product_price,
                                "surplus_after_purchase": scenario_savings - product_price,
                            }
                        else:
                            # Compare new monthly surplus against monthly cost
                            can_afford = monthly_surplus >= product_price
                            affordability_details = {
                                "comparison": "monthly_surplus vs monthly_cost",
                                "monthly_surplus": monthly_surplus,
                                "monthly_cost": product_price,
                            }
                    else:
                        # No scenario - use current financial state
                        if not historical:
                            historical = await _get_historical_averages(db, months_back=3)

                        if is_one_time_purchase:
                            # For one-time purchase without scenario, check if current surplus * reasonable months covers it
                            months_needed = product_price / historical["avg_monthly_surplus"] if historical["avg_monthly_surplus"] > 0 else float('inf')
                            can_afford = months_needed <= 12  # Reasonable timeframe
                            affordability_details = {
                                "comparison": "current_savings_rate",
                                "avg_monthly_surplus": historical["avg_monthly_surplus"],
                                "months_to_save": round(months_needed, 1) if months_needed != float('inf') else "Never (no surplus)",
                                "product_total_price": product_price,
                            }
                        else:
                            # Monthly expense - compare against surplus
                            can_afford = historical["avg_monthly_surplus"] >= product_price
                            affordability_details = {
                                "comparison": "monthly_surplus vs monthly_cost",
                                "avg_monthly_surplus": historical["avg_monthly_surplus"],
                                "monthly_cost": product_price,
                            }

                    # Generate recommendation
                    if can_afford:
                        if is_one_time_purchase and scenario_savings > 0:
                            recommendation = f"Yes! With your adjusted spending, you'll save ₹{scenario_savings:,.0f} which covers the ₹{product_price:,.0f} cost."
                        elif is_one_time_purchase:
                            months = affordability_details.get("months_to_save", "unknown")
                            recommendation = f"At your current savings rate, you can afford this in about {months} months."
                        else:
                            recommendation = "This fits within your monthly surplus."
                    else:
                        if is_one_time_purchase and scenario_savings > 0:
                            shortfall = product_price - scenario_savings
                            recommendation = f"You'll be ₹{shortfall:,.0f} short. Consider extending the savings period or reducing more."
                        else:
                            recommendation = "This would exceed your current surplus. Consider cutting other expenses first."

                    results.append(OperationResult(
                        operation_type=op.type,
                        success=True,
                        data={
                            "product": product_name,
                            "product_price": product_price,
                            "is_one_time_purchase": is_one_time_purchase,
                            "can_afford": can_afford,
                            "recommendation": recommendation,
                            "scenario_applied": scenario_savings > 0,
                            **affordability_details,
                        }
                    ))
                else:
                    results.append(OperationResult(
                        operation_type=op.type,
                        success=False,
                        error=f"Could not determine price for {product_name}. Try specifying the amount."
                    ))

            elif op.type == OperationType.SAVINGS_ADVICE:
                health = accumulated_context.get("health") or await calculate_financial_health(db, offset=0)
                trends = accumulated_context.get("trends") or await get_trends_overview(db)

                increasing = [(c.category, c.change_percent) for c in trends.category_trends if c.trend == "increasing"][:3]
                categories = health.get("category_breakdown", [])

                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data={
                        "increasing_categories": increasing,
                        "top_expense": categories[0] if categories else None,
                        "burn_status": health["burn_rate_status"],
                        "remaining_budget": health["budget_remaining"],
                    }
                ))

            elif op.type == OperationType.CUSTOM_SCENARIO:
                result = await _execute_custom_scenario(db, op.params, accumulated_context)
                results.append(result)

            # ============================================
            # New Operation Handlers
            # ============================================

            elif op.type == OperationType.TIME_RANGE_SPEND:
                # Calculate spending for a specific time range
                category_name = op.params.get("category_name")
                months_back = op.params.get("months_back")
                relative = op.params.get("relative")
                start_date = op.params.get("start_date")
                end_date = op.params.get("end_date")

                result_data = await chatbot_compute.calculate_time_range_spend(
                    db,
                    category_name=category_name,
                    months_back=months_back,
                    relative=relative,
                    start_date=start_date,
                    end_date=end_date,
                )
                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data=result_data
                ))
                accumulated_context["time_range_spend"] = result_data

            elif op.type == OperationType.AVERAGE_SPENDING:
                # Get average monthly spending by category
                category_name = op.params.get("category_name")
                months_back = op.params.get("months_back", 3)

                result_data = await chatbot_compute.get_avg_spending_by_category(
                    db,
                    category_name=category_name,
                    months_back=months_back,
                )
                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data=result_data
                ))
                accumulated_context["avg_spending"] = result_data

            elif op.type == OperationType.SPENDING_VELOCITY:
                # Get rate of spending change
                window_days = op.params.get("window_days", 7)

                result_data = await chatbot_compute.get_spending_velocity(
                    db,
                    window_days=window_days,
                )
                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data=result_data
                ))
                accumulated_context["velocity"] = result_data

            elif op.type == OperationType.FUTURE_PROJECTION:
                # Project future spending/savings
                months_forward = op.params.get("months_forward", 6)
                adjustments_raw = op.params.get("adjustments", [])

                # Convert list of adjustments to dict
                adjustments = {}
                if adjustments_raw:
                    for adj in adjustments_raw:
                        if isinstance(adj, dict):
                            adjustments[adj.get("category", "")] = adj.get("change_amount", 0)

                result_data = await chatbot_compute.project_future_spending(
                    db,
                    months_forward=months_forward,
                    adjustments=adjustments if adjustments else None,
                )
                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data=result_data
                ))
                # Store for chained operations
                accumulated_context["scenario_savings"] = result_data["total_projected_savings"]
                accumulated_context["monthly_surplus"] = result_data["new_monthly_surplus"]

            elif op.type == OperationType.GOAL_PLANNING:
                # Plan to reach a savings goal
                target_amount = op.params.get("target_amount", 0)
                target_months = op.params.get("target_months")
                goal_name = op.params.get("goal_name")

                result_data = await chatbot_compute.calculate_goal_plan(
                    db,
                    target_amount=target_amount,
                    target_months=target_months,
                    goal_name=goal_name,
                )
                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data=result_data
                ))
                accumulated_context["goal_plan"] = result_data

            elif op.type == OperationType.BUDGET_FORECAST:
                # Forecast budget status for end of cycle
                days_forward = op.params.get("days_forward", 0)

                result_data = await chatbot_compute.forecast_budget_status(
                    db,
                    days_forward=days_forward,
                )
                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data=result_data
                ))
                accumulated_context["forecast"] = result_data

            elif op.type == OperationType.CLARIFY:
                results.append(OperationResult(
                    operation_type=op.type,
                    success=True,
                    data={"question": op.params.get("question", "Could you please provide more details?")}
                ))

        except Exception as e:
            results.append(OperationResult(
                operation_type=op.type,
                success=False,
                error=str(e)
            ))

    return results


async def _format_conversational_response(
    user_query: str,
    plan: QueryPlan,
    results: List[OperationResult]
) -> str:
    """
    Format operation results into a natural conversational response using LLM.
    """
    # Build structured context from results
    results_summary = []
    key_facts = []

    for r in results:
        if r.success:
            results_summary.append(f"- {r.operation_type.value}: {r.data}")

            # Extract key facts for clearer formatting
            if r.operation_type == OperationType.CUSTOM_SCENARIO:
                d = r.data
                key_facts.append(f"With the spending adjustments, monthly surplus increases by ₹{d.get('additional_monthly_savings', 0):,.0f}")
                key_facts.append(f"Over {d.get('months_projected', 0)} months, total projected savings: ₹{d.get('total_projected_savings', 0):,.0f}")
            elif r.operation_type == OperationType.AFFORDABILITY_CHECK:
                d = r.data
                product = d.get('product', 'the item')
                price = d.get('product_price', 0)
                can_afford = d.get('can_afford', False)
                key_facts.append(f"{product} costs approximately ₹{price:,.0f}")
                key_facts.append(f"Affordable: {'Yes' if can_afford else 'No'}")
                if d.get('recommendation'):
                    key_facts.append(f"Recommendation: {d.get('recommendation')}")
            elif r.operation_type == OperationType.TIME_RANGE_SPEND:
                d = r.data
                total = d.get('total', 0)
                cat = d.get('matched_category') or d.get('category_filter') or 'all categories'
                period = d.get('period', {})
                key_facts.append(f"Total spent on {cat}: ₹{total:,.0f}")
                key_facts.append(f"Period: {period.get('start', '')} to {period.get('end', '')}")
            elif r.operation_type == OperationType.AVERAGE_SPENDING:
                d = r.data
                if d.get('requested_category'):
                    cat_data = d['requested_category']
                    key_facts.append(f"Average monthly spending on {cat_data['name']}: ₹{cat_data['avg_monthly']:,.0f}")
                key_facts.append(f"Overall average monthly: ₹{d.get('avg_monthly_total', 0):,.0f}")
            elif r.operation_type == OperationType.SPENDING_VELOCITY:
                d = r.data
                key_facts.append(f"Spending change: {d.get('change_percent', 0):+.1f}% ({d.get('status', 'unknown')})")
                key_facts.append(f"Current week: ₹{d.get('current_window', {}).get('spending', 0):,.0f}")
            elif r.operation_type == OperationType.FUTURE_PROJECTION:
                d = r.data
                key_facts.append(f"Projected savings over {d.get('months_projected', 0)} months: ₹{d.get('total_projected_savings', 0):,.0f}")
                key_facts.append(f"New monthly surplus: ₹{d.get('new_monthly_surplus', 0):,.0f}")
            elif r.operation_type == OperationType.GOAL_PLANNING:
                d = r.data
                key_facts.append(f"Target amount: ₹{d.get('target_amount', 0):,.0f}")
                if d.get('is_feasible'):
                    if d.get('months_needed'):
                        key_facts.append(f"Achievable in {d.get('months_needed')} months at current rate")
                    else:
                        key_facts.append(f"Required monthly savings: ₹{d.get('required_monthly_savings', 0):,.0f}")
                else:
                    key_facts.append(f"Shortfall per month: ₹{d.get('shortfall_per_month', 0):,.0f}")
            elif r.operation_type == OperationType.BUDGET_FORECAST:
                d = r.data
                key_facts.append(f"Forecast: {d.get('message', '')}")
                key_facts.append(f"Projected remaining: ₹{d.get('projected_remaining', 0):,.0f}")
        else:
            results_summary.append(f"- {r.operation_type.value}: Failed - {r.error}")

    key_facts_str = "\n".join(f"  • {f}" for f in key_facts) if key_facts else "None"

    prompt = f"""User asked: "{user_query}"

Query analysis: {plan.query_summary}

KEY FACTS (use these numbers in your response):
{key_facts_str}

Full computed results:
{chr(10).join(results_summary)}

Write a natural, conversational response (3-5 sentences) that directly answers the user's question.
IMPORTANT:
- Lead with the answer (yes/no for affordability questions)
- Include specific numbers with ₹ symbol
- Explain the calculation briefly (e.g., "By reducing food by ₹10k/month, you'll save ₹X over Y months")
- If affordable, confirm it confidently. If not, suggest alternatives.
- Write in flowing prose, not bullet points"""

    response = await _call_gemini_api(
        prompt,
        system_instruction="You are a friendly financial assistant. Give clear, confident, conversational responses with specific numbers.",
        temperature=0.5  # Allow some creativity for natural responses
    )

    if not _is_valid_llm_response(response):
        # Fallback: build structured response from results
        fallback_parts = []
        for r in results:
            if r.success and r.data:
                if r.operation_type == OperationType.BUDGET_STATUS:
                    fallback_parts.append(f"Budget: ₹{r.data.get('budget', 0):,.0f}, Spent: ₹{r.data.get('spent', 0):,.0f}, Remaining: ₹{r.data.get('remaining', 0):,.0f}")
                elif r.operation_type == OperationType.CUSTOM_SCENARIO:
                    d = r.data
                    fallback_parts.append(
                        f"By adjusting your spending, you'll save an additional ₹{d.get('additional_monthly_savings', 0):,.0f}/month. "
                        f"Over {d.get('months_projected', 0)} months, that's ₹{d.get('total_projected_savings', 0):,.0f} in total savings."
                    )
                elif r.operation_type == OperationType.AFFORDABILITY_CHECK:
                    d = r.data
                    answer = "Yes" if d.get('can_afford') else "No"
                    product = d.get('product', 'item')
                    price = d.get('product_price', 0)
                    fallback_parts.append(f"{answer}, you can{'not' if not d.get('can_afford') else ''} afford {product} (₹{price:,.0f}). {d.get('recommendation', '')}")
                elif r.operation_type == OperationType.TIME_RANGE_SPEND:
                    d = r.data
                    cat = d.get('matched_category') or d.get('category_filter') or 'total'
                    fallback_parts.append(f"You spent ₹{d.get('total', 0):,.0f} on {cat} ({d.get('transaction_count', 0)} transactions).")
                elif r.operation_type == OperationType.AVERAGE_SPENDING:
                    d = r.data
                    if d.get('requested_category') and d['requested_category'].get('found'):
                        cat_data = d['requested_category']
                        fallback_parts.append(f"Your average monthly spending on {cat_data['name']} is ₹{cat_data['avg_monthly']:,.0f}.")
                    else:
                        fallback_parts.append(f"Average monthly spending: ₹{d.get('avg_monthly_total', 0):,.0f}.")
                elif r.operation_type == OperationType.SPENDING_VELOCITY:
                    d = r.data
                    status = d.get('status', 'stable')
                    change = d.get('change_percent', 0)
                    fallback_parts.append(f"Your spending is {status} ({change:+.1f}% vs last week).")
                elif r.operation_type == OperationType.FUTURE_PROJECTION:
                    d = r.data
                    fallback_parts.append(
                        f"Projected savings over {d.get('months_projected', 0)} months: ₹{d.get('total_projected_savings', 0):,.0f} "
                        f"(₹{d.get('new_monthly_surplus', 0):,.0f}/month)."
                    )
                elif r.operation_type == OperationType.GOAL_PLANNING:
                    d = r.data
                    goal = d.get('goal_name') or f"₹{d.get('target_amount', 0):,.0f}"
                    if d.get('is_feasible'):
                        if d.get('months_needed'):
                            fallback_parts.append(f"You can reach {goal} in {d.get('months_needed')} months at your current savings rate.")
                        else:
                            fallback_parts.append(f"To reach {goal} in {d.get('target_months')} months, save ₹{d.get('required_monthly_savings', 0):,.0f}/month.")
                    else:
                        fallback_parts.append(f"Reaching {goal} requires cutting ₹{d.get('shortfall_per_month', 0):,.0f}/month more.")
                elif r.operation_type == OperationType.BUDGET_FORECAST:
                    d = r.data
                    fallback_parts.append(d.get('message', 'Budget forecast unavailable.'))
                elif r.operation_type == OperationType.CLARIFY:
                    fallback_parts.append(r.data.get("question", "Could you provide more details?"))

        return " ".join(fallback_parts) if fallback_parts else "I analyzed your query but couldn't generate a response. Please try rephrasing."

    return response


async def _legacy_process_chat_message(db: AsyncSession, message: str, session_id: str = "") -> Dict[str, Any]:
    """
    Legacy regex-based chat processing. Used as fallback when LLM-based analysis fails.
    """
    intent, params = detect_intent(message)

    handlers = {
        "budget_status": lambda: handle_budget_status(db, message),
        "category_spend": lambda: handle_category_spend(db, params.get("category", ""), message),
        "trends": lambda: handle_trends(db, message),
        "savings_advice": lambda: handle_savings_advice(db, message),
        "affordability": lambda: handle_affordability(db, params.get("raw_query", message)),
        "time_range_spend": lambda: handle_time_range_spend(db, params.get("category"), params.get("months_back", 1), message),
        "goal_planning": lambda: handle_goal_planning(db, params.get("target_amount", 0), params.get("target_months"), message),
        "budget_forecast": lambda: handle_budget_forecast(db, message),
        "average_spending": lambda: handle_average_spending(db, params.get("category"), message),
        "spending_velocity": lambda: handle_spending_velocity(db, message),
        "general": lambda: handle_general(db, params.get("raw_query", message)),
    }

    handler = handlers.get(intent, handlers["general"])
    response = await handler()

    return {
        "response": response,
        "intent": intent,
        "requires_llm": intent in ("affordability", "budget_status", "category_spend", "trends", "savings_advice",
                                   "time_range_spend", "goal_planning", "budget_forecast", "average_spending", "spending_velocity"),
        "rate_limit": get_rate_limit_status(),
        "session_id": session_id,
    }


# Intent Handlers (All compute locally, only use LLM for formatting)

async def handle_budget_status(db: AsyncSession, user_query: str = "") -> str:
    """Handle budget status query - all local computation with optional LLM formatting."""
    try:
        health = await calculate_financial_health(db, offset=0)

        # Structured data for LLM formatting
        data = {
            "budget": health['total_budget'],
            "spent": health['total_spend'],
            "remaining": health['budget_remaining'],
            "days_left": health['days_left'],
            "safe_daily": health['safe_to_spend_daily'],
            "status": health['burn_rate_status'],
        }

        # Fallback bullet-point response
        fallback = (
            f"Your current budget status:\n"
            f"- Budget: ₹{health['total_budget']:,.2f}\n"
            f"- Spent: ₹{health['total_spend']:,.2f}\n"
            f"- Remaining: ₹{health['budget_remaining']:,.2f}\n"
            f"- Days left: {health['days_left']}\n"
            f"- Safe to spend daily: ₹{health['safe_to_spend_daily']:,.2f}\n"
            f"- Status: {health['burn_rate_status']}"
        )

        # Try LLM formatting if query provided
        if user_query:
            formatted = await _format_response_with_llm(data, user_query)
            if _is_valid_llm_response(formatted):
                return formatted

        return fallback
    except Exception as e:
        return f"Unable to fetch budget status. Please try again later. (Error: {str(e)})"


async def handle_category_spend(db: AsyncSession, category: str, user_query: str = "") -> str:
    """Handle category spending query - local lookup with optional LLM formatting."""
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
            data = {
                "category": matched['name'],
                "amount": matched['value'],
                "total_spend": health['total_spend'],
                "percentage": (matched['value'] / health['total_spend'] * 100) if health['total_spend'] > 0 else 0,
            }

            fallback = f"Your spending on {matched['name']} this cycle: ₹{matched['value']:,.2f}"

            if user_query:
                formatted = await _format_response_with_llm(data, user_query)
                if _is_valid_llm_response(formatted):
                    return formatted

            return fallback
        else:
            cat_list = ", ".join([c["name"] for c in categories[:5]])
            return f"No category matching '{category}' found. Your top categories: {cat_list}"
    except Exception as e:
        return f"Unable to fetch category spending. Please try again later. (Error: {str(e)})"


async def handle_trends(db: AsyncSession, user_query: str = "") -> str:
    """Handle trends query - local computation with optional LLM formatting."""
    try:
        trends = await get_trends_overview(db)

        if not trends.category_trends:
            return "Not enough data to analyze trends yet."

        # Build summary locally
        increasing = [c.category for c in trends.category_trends if c.trend == "increasing"][:3]
        decreasing = [c.category for c in trends.category_trends if c.trend == "decreasing"][:3]

        high_spend_months = [p.month_name for p in trends.seasonal_patterns if p.is_high_spend]

        data = {
            "increasing_categories": increasing,
            "decreasing_categories": decreasing,
            "high_spend_months": high_spend_months,
            "top_recurring": trends.recurring_patterns[0].merchant_name if trends.recurring_patterns else None,
        }

        # Fallback response
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

        if user_query:
            formatted = await _format_response_with_llm(data, user_query)
            if _is_valid_llm_response(formatted):
                return formatted

        return response
    except Exception as e:
        return f"Unable to fetch spending trends. Please try again later. (Error: {str(e)})"


async def handle_savings_advice(db: AsyncSession, user_query: str = "") -> str:
    """Handle savings advice query - local analysis with optional LLM formatting."""
    try:
        health = await calculate_financial_health(db, offset=0)
        trends = await get_trends_overview(db)

        # Build data for LLM
        increasing = [c for c in trends.category_trends if c.trend == "increasing"]
        categories = health.get("category_breakdown", [])

        data = {
            "increasing_categories": [(c.category, c.change_percent) for c in increasing[:3]],
            "top_expense": categories[0] if categories else None,
            "burn_status": health["burn_rate_status"],
            "remaining_budget": health["budget_remaining"],
        }

        # Fallback advice
        advice = ["Here are some savings suggestions:"]

        if increasing:
            top = increasing[0]
            advice.append(
                f"- {top.category} spending increased {top.change_percent:.0f}% - consider reviewing"
            )

        if categories:
            top_cat = categories[0]
            advice.append(f"- Your biggest expense: {top_cat['name']} (₹{top_cat['value']:,.0f})")

        if health["burn_rate_status"] in ["High Burn", "Caution"]:
            advice.append(f"- Current status: {health['burn_rate_status']} - slow down spending")

        fallback = "\n".join(advice)

        if user_query:
            formatted = await _format_response_with_llm(data, user_query)
            if _is_valid_llm_response(formatted):
                return formatted

        return fallback
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

        # Build data for LLM formatting
        data = {
            "product": product,
            "can_afford": result.can_afford,
            "monthly_cost": price,
            "budget": result.current_budget,
            "current_spend": result.current_avg_spend,
            "projected_spend": result.projected_spend_with_new,
            "impact_percent": result.impact_percent,
            "recommendation": result.recommendation,
        }

        # Bullet-point fallback
        status = "Yes" if result.can_afford else "No"
        fallback = (
            f"Can you afford {product}?\n"
            f"- Answer: {status}\n"
            f"- Estimated monthly cost: ₹{price:,.0f}\n"
            f"- Your budget: ₹{result.current_budget:,.0f}\n"
            f"- Current avg spend: ₹{result.current_avg_spend:,.0f}\n"
            f"- With new expense: ₹{result.projected_spend_with_new:,.0f}\n"
            f"- Budget impact: {result.impact_percent:.1f}%\n"
            f"- {result.recommendation}"
        )

        # Try LLM formatting
        formatted = await _format_response_with_llm(data, raw_query)
        if _is_valid_llm_response(formatted):
            return formatted

        return fallback
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
        "- 'Where can I save money?' - Savings suggestions\n"
        "- 'Can I save ₹50,000 in 6 months?' - Goal planning\n"
        "- 'Will I stay under budget?' - Budget forecast\n"
        "- 'What's my average food spending?' - Average spending\n\n"
        "Try asking one of these!"
    )


# New intent handlers for predictive queries

async def handle_time_range_spend(db: AsyncSession, category: str, months_back: int, user_query: str = "") -> str:
    """Handle time range spending query."""
    try:
        result = await chatbot_compute.calculate_time_range_spend(
            db,
            category_name=category,
            months_back=months_back,
        )

        cat_name = result.get('matched_category') or category or 'all categories'
        total = result.get('total', 0)
        count = result.get('transaction_count', 0)
        period = result.get('period', {})

        data = {
            "category": cat_name,
            "total": total,
            "count": count,
            "period_start": period.get('start'),
            "period_end": period.get('end'),
            "months": months_back,
        }

        fallback = f"You spent ₹{total:,.0f} on {cat_name} over the past {months_back} month(s) ({count} transactions)."

        if user_query:
            formatted = await _format_response_with_llm(data, user_query)
            if _is_valid_llm_response(formatted):
                return formatted

        return fallback
    except Exception as e:
        return f"Unable to calculate spending for period. (Error: {str(e)})"


async def handle_goal_planning(db: AsyncSession, target_amount: float, target_months: int = None, user_query: str = "") -> str:
    """Handle goal planning query."""
    try:
        result = await chatbot_compute.calculate_goal_plan(
            db,
            target_amount=target_amount,
            target_months=target_months,
        )

        data = {
            "target": target_amount,
            "is_feasible": result.get('is_feasible'),
            "months_needed": result.get('months_needed'),
            "required_monthly": result.get('required_monthly_savings'),
            "shortfall": result.get('shortfall_per_month'),
            "suggestions": result.get('suggestions', []),
        }

        if result.get('is_feasible'):
            if result.get('months_needed'):
                fallback = f"You can save ₹{target_amount:,.0f} in about {result['months_needed']:.1f} months at your current rate."
            else:
                fallback = f"To save ₹{target_amount:,.0f} in {target_months} months, you need to save ₹{result.get('required_monthly_savings', 0):,.0f}/month."
        else:
            shortfall = result.get('shortfall_per_month', 0)
            fallback = f"To reach ₹{target_amount:,.0f}, you need to cut ₹{shortfall:,.0f}/month more from your spending."
            if result.get('suggestions'):
                fallback += "\nSuggestions: " + ", ".join(
                    f"reduce {s['category']} by ₹{s['suggested_reduction']:,.0f}"
                    for s in result['suggestions'][:2]
                )

        if user_query:
            formatted = await _format_response_with_llm(data, user_query)
            if _is_valid_llm_response(formatted):
                return formatted

        return fallback
    except Exception as e:
        return f"Unable to create goal plan. (Error: {str(e)})"


async def handle_budget_forecast(db: AsyncSession, user_query: str = "") -> str:
    """Handle budget forecast query."""
    try:
        result = await chatbot_compute.forecast_budget_status(db)

        data = {
            "status": result.get('status'),
            "message": result.get('message'),
            "current_spend": result.get('current_spend'),
            "projected_total": result.get('projected_total_spend'),
            "projected_remaining": result.get('projected_remaining'),
            "days_left": result.get('days_left_in_cycle'),
            "safe_daily": result.get('safe_daily_spend'),
            "velocity": result.get('spending_velocity_status'),
        }

        fallback = result.get('message', 'Unable to forecast budget.')
        if result.get('safe_daily_spend'):
            fallback += f" Safe to spend: ₹{result['safe_daily_spend']:,.0f}/day."

        if user_query:
            formatted = await _format_response_with_llm(data, user_query)
            if _is_valid_llm_response(formatted):
                return formatted

        return fallback
    except Exception as e:
        return f"Unable to forecast budget. (Error: {str(e)})"


async def handle_average_spending(db: AsyncSession, category: str, user_query: str = "") -> str:
    """Handle average spending query."""
    try:
        result = await chatbot_compute.get_avg_spending_by_category(
            db,
            category_name=category,
            months_back=3,
        )

        if category and result.get('requested_category'):
            cat_data = result['requested_category']
            if cat_data.get('found'):
                fallback = f"Your average monthly spending on {cat_data['name']} is ₹{cat_data['avg_monthly']:,.0f}."
            else:
                fallback = f"Category '{category}' not found. Your average monthly total is ₹{result['avg_monthly_total']:,.0f}."
        else:
            fallback = f"Your average monthly spending is ₹{result['avg_monthly_total']:,.0f}."

        data = {
            "category": category,
            "avg_monthly_total": result.get('avg_monthly_total'),
            "requested_category": result.get('requested_category'),
            "months_analyzed": result.get('months_analyzed'),
        }

        if user_query:
            formatted = await _format_response_with_llm(data, user_query)
            if _is_valid_llm_response(formatted):
                return formatted

        return fallback
    except Exception as e:
        return f"Unable to calculate average spending. (Error: {str(e)})"


async def handle_spending_velocity(db: AsyncSession, user_query: str = "") -> str:
    """Handle spending velocity query."""
    try:
        result = await chatbot_compute.get_spending_velocity(db, window_days=7)

        status = result.get('status', 'stable')
        change = result.get('change_percent', 0)
        current = result.get('current_window', {}).get('spending', 0)
        previous = result.get('previous_window', {}).get('spending', 0)

        data = {
            "status": status,
            "change_percent": change,
            "current_week": current,
            "previous_week": previous,
        }

        status_text = {
            "increasing_fast": "increasing rapidly",
            "increasing": "increasing",
            "decreasing_fast": "decreasing rapidly",
            "decreasing": "decreasing",
            "stable": "stable",
        }.get(status, status)

        fallback = f"Your spending is {status_text} ({change:+.1f}% vs last week). This week: ₹{current:,.0f}, last week: ₹{previous:,.0f}."

        if user_query:
            formatted = await _format_response_with_llm(data, user_query)
            if _is_valid_llm_response(formatted):
                return formatted

        return fallback
    except Exception as e:
        return f"Unable to analyze spending velocity. (Error: {str(e)})"


async def process_chat_message(
    db: AsyncSession,
    message: str,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for chat messages.
    Uses LLM-based conversational processing with fallback to legacy regex system.

    Args:
        db: Database session
        message: User's message
        session_id: Optional session ID for multi-turn conversations

    Returns:
        Response dict with response text, intent, rate limit info, and session_id
    """
    # Get or create session for conversation continuity
    session = _session_manager.get_or_create_session(session_id)

    # Add user message to session history
    session.add_message("user", message)

    # Check if we have enough rate limit for conversational flow
    has_quota, quota_error = _check_rate_limit_for_conversation()

    if has_quota:
        try:
            # Try new conversational flow with session context
            plan = await _analyze_query_with_llm_v2(db, message, session)

            if plan:
                # Check if clarification is needed
                if plan.requires_clarification and plan.clarification_question:
                    response_text = plan.clarification_question
                    session.add_message("assistant", response_text)
                    return {
                        "response": response_text,
                        "intent": "clarify",
                        "requires_llm": True,
                        "rate_limit": get_rate_limit_status(),
                        "session_id": session.session_id,
                    }

                # Execute the operations
                results = await _execute_operations(db, plan.operations)

                # Store results in session for follow-up queries
                session.last_results = {
                    "operations": [op.model_dump() for op in plan.operations],
                    "results": [r.model_dump() for r in results],
                }

                # Check if any operation is a clarification request
                for r in results:
                    if r.operation_type == OperationType.CLARIFY and r.success:
                        response_text = r.data.get("question", "Could you provide more details?")
                        session.add_message("assistant", response_text)
                        return {
                            "response": response_text,
                            "intent": "clarify",
                            "requires_llm": True,
                            "rate_limit": get_rate_limit_status(),
                            "session_id": session.session_id,
                        }

                # Format the response conversationally
                response_text = await _format_conversational_response(message, plan, results)

                # Add assistant response to session
                session.add_message("assistant", response_text)

                return {
                    "response": response_text,
                    "intent": "conversational",
                    "requires_llm": True,
                    "rate_limit": get_rate_limit_status(),
                    "session_id": session.session_id,
                }

        except Exception:
            # Fall through to legacy system on any error
            pass

    # Fallback to legacy regex-based system
    result = await _legacy_process_chat_message(db, message, session.session_id)

    # Add assistant response to session
    session.add_message("assistant", result["response"])

    return result


async def _analyze_query_with_llm_v2(
    db: AsyncSession,
    user_query: str,
    session: ConversationSession
) -> Optional[QueryPlan]:
    """
    Enhanced query analyzer with session context for multi-turn conversations.

    Uses conversation history to understand follow-up queries like:
    - "What about last month?" (refers to previous category query)
    - "And for food?" (refers to previous time range query)
    """
    # Get context for the LLM
    categories = await _get_categories(db)
    context = await _get_financial_context(db)
    historical = await _get_historical_averages(db, months_back=3)

    # Format category spend for context
    top_cat_spend = sorted(historical['avg_category_spend'].items(), key=lambda x: x[1], reverse=True)[:5]
    cat_spend_str = ", ".join([f"{cat}: ₹{amt:,.0f}" for cat, amt in top_cat_spend])

    # Include conversation history for follow-up queries
    conversation_context = session.get_history_for_llm()

    prompt = f"""You are a financial assistant. Parse the user's question into operations to execute.

CONVERSATION HISTORY (for context on follow-up queries):
{conversation_context}

Available operations:
1. budget_status - Get current budget, spending, and remaining amount
2. category_spend (params: category_name) - Get spending for a specific category
3. trends_overview - Get spending trends analysis
4. affordability_check (params: product_name, monthly_cost) - Check if user can afford something
   - The system will automatically look up the price if monthly_cost=0
5. savings_advice - Get savings suggestions
6. custom_scenario (params: adjustments, months) - Project future savings with spending changes
   - adjustments: list of {{"category": "name", "change_amount": -5000}} (negative = reduction)
   - months: number of months to project
7. time_range_spend (params: category_name, months_back, relative) - Spending for a specific period
   - relative can be: "last_week", "this_month", "last_3_months", etc.
8. average_spending (params: category_name, months_back) - Average monthly spending
9. spending_velocity (params: window_days) - Rate of spending change
10. future_projection (params: months_forward, adjustments) - Project future spending/savings
11. goal_planning (params: target_amount, target_months, goal_name) - Plan to reach a savings goal
12. budget_forecast (params: days_forward) - Forecast budget status for end of cycle

User's categories: {', '.join(categories) if categories else 'Unknown'}

HISTORICAL AVERAGES (past 3 months - USE THESE FOR PROJECTIONS):
- Average monthly budget: ₹{historical['avg_monthly_budget']:,.0f}
- Average monthly spend: ₹{historical['avg_monthly_spend']:,.0f}
- Average monthly surplus (budget - spend): ₹{historical['avg_monthly_surplus']:,.0f}
- Average spend by top categories: {cat_spend_str}

Current cycle: Budget ₹{context['budget']:,.0f}, Spent ₹{context['spent']:,.0f}, Days left: {context['days_left']}

HANDLING FOLLOW-UP QUERIES:
- If the user says "what about X?" or "and for X?", check the conversation history
- Use the same operation type but with the new parameter (category, time range, etc.)
- Example: If previous was "food spending last month" and user asks "what about entertainment?",
  use time_range_spend with category_name="Entertainment"

EXAMPLES:
Input: "How much have I spent on fuel in the past 3 months?"
Output: {{"query_summary": "Fuel spending over 3 months", "operations": [{{"type": "time_range_spend", "params": {{"category_name": "Fuel", "months_back": 3}}, "description": "Calculate fuel spending for past 3 months"}}], "requires_clarification": false, "clarification_question": null}}

Input: "Can I save 50k in 6 months?"
Output: {{"query_summary": "Goal planning for 50k in 6 months", "operations": [{{"type": "goal_planning", "params": {{"target_amount": 50000, "target_months": 6}}, "description": "Plan to save 50,000 rupees in 6 months"}}], "requires_clarification": false, "clarification_question": null}}

Input: "Will I stay under budget?"
Output: {{"query_summary": "Budget forecast for current cycle", "operations": [{{"type": "budget_forecast", "params": {{}}, "description": "Forecast if user will stay under budget"}}], "requires_clarification": false, "clarification_question": null}}

User query: "{user_query}" """

    response = await _call_gemini_api(
        prompt,
        system_instruction="You are a financial query analyzer. Output valid JSON only.",
        response_schema=_get_query_plan_schema(),
        temperature=0  # Deterministic for structured output
    )

    if not response or not _is_valid_llm_response(response):
        # Fall back to the original analyzer
        return await _analyze_query_with_llm(db, user_query)

    try:
        # Clean up response - remove markdown code blocks if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        data = json.loads(cleaned)

        # Parse operations
        operations = []
        for op_data in data.get("operations", []):
            try:
                op_type = OperationType(op_data.get("type", "clarify"))
                operations.append(Operation(
                    type=op_type,
                    params=op_data.get("params", {}),
                    description=op_data.get("description", "")
                ))
            except ValueError:
                # Invalid operation type, skip
                continue

        if not operations:
            return await _analyze_query_with_llm(db, user_query)

        return QueryPlan(
            operations=operations,
            requires_clarification=data.get("requires_clarification", False),
            clarification_question=data.get("clarification_question"),
            query_summary=data.get("query_summary", user_query)
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return await _analyze_query_with_llm(db, user_query)
