"""Gemini LLM client for agent system.

Extracted from chatbot.py for reuse across parser and aggregator agents.
"""

import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from backend/.env
_env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
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


def check_rate_limit_for_conversation() -> Tuple[bool, str]:
    """Check if we have enough rate limit quota for a full conversation flow.

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


async def call_gemini_api(
    prompt: str,
    system_instruction: str = "",
    response_schema: Optional[Dict[str, Any]] = None,
    temperature: float = 0.7,
    timeout: float = 30.0,
) -> Optional[str]:
    """Call Gemini API for LLM tasks.

    Args:
        prompt: The prompt to send to the model
        system_instruction: Optional system instruction for the model
        response_schema: Optional JSON schema to enforce structured output
        temperature: Model temperature (0 = deterministic, 1 = creative)
        timeout: Request timeout in seconds

    Returns:
        Response text or None on failure
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("[LLM] GEMINI_API_KEY not found in environment")
        return None

    allowed, status = _check_rate_limit()
    if not allowed:
        logger.warning(f"[LLM] Rate limit exceeded: {status}")
        return f"Rate limit exceeded: {status.get('error', 'Try again later.')}"

    logger.debug(f"[LLM] Making API call (rate limit status: {status})")

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
        async with httpx.AsyncClient(timeout=timeout) as client:
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
        logger.error(f"[LLM] HTTP error: {e.response.status_code} - {error_detail}")
        return f"API error: {e.response.status_code} - {error_detail}"
    except Exception as e:
        logger.exception(f"[LLM] Exception during API call: {e}")
        return f"Error calling LLM: {str(e)}"


def is_valid_llm_response(response: Optional[str]) -> bool:
    """Check if LLM response is valid and usable."""
    if not response:
        return False
    # Check for error prefixes
    error_prefixes = ("API error:", "Error calling LLM:", "Rate limit exceeded:")
    if response.startswith(error_prefixes):
        return False
    # Check for dict string representation (indicates fallback failure)
    if response.startswith("{") and response.endswith("}"):
        try:
            import json
            json.loads(response)
            # Valid JSON is actually OK for structured responses
            return True
        except json.JSONDecodeError:
            return False
    return True


async def extract_product_price(product_query: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """Use LLM to extract product name and estimated price.

    Only the product name is sent to LLM, not financial data.

    Returns:
        Tuple of (product_name, price, error_message)
    """
    prompt = f"""Extract the product name and estimate its price in INR from this query: "{product_query}"

Return ONLY in this exact format (no other text):
Product: [product name]
Price: [estimated monthly cost or EMI in INR as a number]
Type: [one-time or monthly]

If it's a one-time purchase, estimate a reasonable EMI (12-month).
If you cannot determine the product or price, return:
Product: unknown
Price: 0
Type: unknown"""

    response = await call_gemini_api(prompt)
    if not response:
        return None, None, "No response from LLM. Check if GEMINI_API_KEY is configured in backend/.env"

    # Check if response is an error message from the API
    error_prefixes = ["API error:", "Error calling LLM:", "Rate limit exceeded:"]
    for prefix in error_prefixes:
        if response.startswith(prefix):
            return None, None, response

    product = None
    price = None
    is_one_time = False

    # Parse response
    response_text = response.strip()

    for line in response_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        line_lower = line.lower()

        if "product" in line_lower and ":" in line:
            product_part = line.split(":", 1)[1].strip()
            product_part = re.sub(r"[\*\#\_\`]", "", product_part).strip()
            if product_part and product_part.lower() != "unknown":
                product = product_part

        elif "price" in line_lower and ":" in line:
            try:
                price_part = line.split(":", 1)[1].strip()
                price_str = re.sub(r"[₹$,\s]", "", price_part)
                match = re.search(r"[\d.]+", price_str)
                if match:
                    price = float(match.group())
            except (ValueError, IndexError):
                price = None

        elif "type" in line_lower and ":" in line:
            type_str = line.split(":", 1)[1].strip().lower()
            is_one_time = "one" in type_str or "total" in type_str

    # Fallback regex patterns
    if not product:
        product_match = re.search(r"product[:\s]+([^\n₹$\d]+)", response_text, re.IGNORECASE)
        if product_match:
            product = product_match.group(1).strip()
            product = re.sub(r"[\*\#\_\`]", "", product).strip()

    if not price:
        price_match = re.search(r"₹?\s*([\d,]+(?:\.\d+)?)\s*(?:INR|rupees?)?", response_text, re.IGNORECASE)
        if price_match:
            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                price = None

    return product, price, None


def get_query_plan_schema() -> Optional[Dict[str, Any]]:
    """Return JSON schema for QueryPlan to enforce structured output from Gemini.

    Note: Returning None disables strict schema validation.
    The Gemini API has strict requirements for object schemas (all properties
    must be explicitly defined), which doesn't work well for dynamic params.
    Instead, we use strong prompting with JSON instructions.
    """
    # Returning None - we'll use prompt-based JSON generation instead of strict schema
    # This is more flexible for handling varied operation params
    return None
