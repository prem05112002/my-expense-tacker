import os
import re
import json
import httpx
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dotenv import load_dotenv

from .. import models
from ..schemas.smart_search import SmartSearchFilters, SmartSearchRequest, SmartSearchResponse
from .transactions import get_filtered_transactions

# Load environment variables from backend/.env
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)

# Date-related keywords for smart search detection
DATE_KEYWORDS = [
    "today", "yesterday", "week", "month", "year", "last", "this", "past",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"
]

# Amount-related patterns
AMOUNT_PATTERNS = [
    r"over\s*₹?\s*\d+",
    r"under\s*₹?\s*\d+",
    r"above\s*₹?\s*\d+",
    r"below\s*₹?\s*\d+",
    r"more\s+than\s*₹?\s*\d+",
    r"less\s+than\s*₹?\s*\d+",
    r"₹\s*\d+",
    r"\d+\s*rupees?"
]


def detect_search_type(query: str, categories: List[str]) -> str:
    """
    Detect if query is a smart search (natural language) or fuzzy search (simple text).
    Returns 'smart' or 'fuzzy'.
    """
    query_lower = query.lower()

    # Check for date keywords
    for keyword in DATE_KEYWORDS:
        if keyword in query_lower:
            return "smart"

    # Check for amount patterns
    for pattern in AMOUNT_PATTERNS:
        if re.search(pattern, query_lower):
            return "smart"

    # Check for category mentions
    for cat in categories:
        if cat.lower() in query_lower:
            return "smart"

    # Check for filter-like phrases
    filter_phrases = [
        "expenses", "spending", "transactions", "payments",
        "show me", "find", "search for", "list",
        "debit", "credit", "income"
    ]
    for phrase in filter_phrases:
        if phrase in query_lower:
            return "smart"

    # Default to fuzzy search for simple queries
    return "fuzzy"


async def _call_gemini_for_filters(query: str, categories: List[str]) -> Optional[Dict[str, Any]]:
    """
    Call Gemini API to parse natural language query into structured filters.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    today = date.today()
    categories_str = ", ".join(categories) if categories else "No categories available"

    prompt = f"""Parse this expense search query into structured filters.

Query: "{query}"

Available categories: {categories_str}
Today's date: {today.isoformat()}

Return ONLY valid JSON with these fields (use null for fields not mentioned):
{{
    "categories": ["category1", "category2"] or null,
    "amount_min": number or null,
    "amount_max": number or null,
    "date_from": "YYYY-MM-DD" or null,
    "date_to": "YYYY-MM-DD" or null,
    "payment_type": "DEBIT" or "CREDIT" or null,
    "merchant_pattern": "pattern" or null
}}

Rules:
- Match category names case-insensitively from the available list
- For "last week", calculate date_from as 7 days ago
- For "last month", calculate date_from as 30 days ago
- For "this month", use first day of current month as date_from
- For specific months like "December", use the full month range
- For "over 500" or "above 500", set amount_min: 500
- For "under 500" or "below 500", set amount_max: 500
- For "expenses" or "spending", set payment_type: "DEBIT"
- For "income" or "salary", set payment_type: "CREDIT"
- Extract merchant names if mentioned (e.g., "swiggy transactions")

Return ONLY the JSON, no explanation."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 500,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
                    # Extract JSON from response (handle markdown code blocks)
                    json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
            return None
    except Exception as e:
        print(f"Error calling Gemini for smart search: {e}")
        return None


def _parse_filters_fallback(query: str, categories: List[str]) -> Dict[str, Any]:
    """
    Local fallback parser for when LLM is unavailable.
    """
    query_lower = query.lower()
    filters: Dict[str, Any] = {
        "categories": None,
        "amount_min": None,
        "amount_max": None,
        "date_from": None,
        "date_to": None,
        "payment_type": None,
        "merchant_pattern": None
    }

    today = date.today()

    # Date parsing
    if "today" in query_lower:
        filters["date_from"] = today.isoformat()
        filters["date_to"] = today.isoformat()
    elif "yesterday" in query_lower:
        yesterday = today - timedelta(days=1)
        filters["date_from"] = yesterday.isoformat()
        filters["date_to"] = yesterday.isoformat()
    elif "last week" in query_lower or "past week" in query_lower:
        filters["date_from"] = (today - timedelta(days=7)).isoformat()
        filters["date_to"] = today.isoformat()
    elif "last month" in query_lower or "past month" in query_lower:
        filters["date_from"] = (today - timedelta(days=30)).isoformat()
        filters["date_to"] = today.isoformat()
    elif "this month" in query_lower:
        filters["date_from"] = today.replace(day=1).isoformat()
        filters["date_to"] = today.isoformat()

    # Amount parsing
    over_match = re.search(r"(?:over|above|more\s+than)\s*₹?\s*(\d+)", query_lower)
    if over_match:
        filters["amount_min"] = float(over_match.group(1))

    under_match = re.search(r"(?:under|below|less\s+than)\s*₹?\s*(\d+)", query_lower)
    if under_match:
        filters["amount_max"] = float(under_match.group(1))

    # Payment type
    if "expense" in query_lower or "spending" in query_lower or "debit" in query_lower:
        filters["payment_type"] = "DEBIT"
    elif "income" in query_lower or "credit" in query_lower or "salary" in query_lower:
        filters["payment_type"] = "CREDIT"

    # Category matching
    matched_cats = []
    for cat in categories:
        if cat.lower() in query_lower:
            matched_cats.append(cat)
    if matched_cats:
        filters["categories"] = matched_cats

    return filters


async def parse_natural_language_query(
    query: str,
    categories: List[str]
) -> SmartSearchFilters:
    """
    Parse a natural language query into structured filters.
    Uses Gemini API with local fallback.
    """
    # Try LLM first
    llm_result = await _call_gemini_for_filters(query, categories)

    if llm_result:
        filters_dict = llm_result
    else:
        # Fallback to local parsing
        filters_dict = _parse_filters_fallback(query, categories)

    # Convert to SmartSearchFilters
    return SmartSearchFilters(
        categories=filters_dict.get("categories"),
        amount_min=filters_dict.get("amount_min"),
        amount_max=filters_dict.get("amount_max"),
        date_from=date.fromisoformat(filters_dict["date_from"]) if filters_dict.get("date_from") else None,
        date_to=date.fromisoformat(filters_dict["date_to"]) if filters_dict.get("date_to") else None,
        payment_type=filters_dict.get("payment_type"),
        merchant_pattern=filters_dict.get("merchant_pattern"),
        is_smart_search=True
    )


async def _get_category_ids_by_names(db: AsyncSession, category_names: List[str]) -> List[int]:
    """Get category IDs from category names (case-insensitive)."""
    if not category_names:
        return []

    stmt = select(models.Category.id, models.Category.name)
    result = await db.execute(stmt)
    all_categories = result.mappings().all()

    category_ids = []
    for cat in all_categories:
        for name in category_names:
            if cat["name"].lower() == name.lower():
                category_ids.append(cat["id"])
                break

    return category_ids


async def get_all_category_names(db: AsyncSession) -> List[str]:
    """Get all category names from database."""
    stmt = select(models.Category.name)
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def process_smart_search(
    db: AsyncSession,
    request: SmartSearchRequest
) -> SmartSearchResponse:
    """
    Main entry point for smart search.
    Detects search type, parses query, and returns filtered results.
    """
    # Get all categories for detection and parsing
    categories = await get_all_category_names(db)

    # Detect search type
    search_type = detect_search_type(request.query, categories)

    if search_type == "fuzzy":
        # Simple fuzzy search - just use the query as search term
        result = await get_filtered_transactions(
            db=db,
            page=request.page,
            limit=request.limit,
            search=request.query,
            sort_by=request.sort_by,
            sort_order=request.sort_order
        )

        return SmartSearchResponse(
            data=result["data"],
            total=result["total"],
            page=result["page"],
            limit=result["limit"],
            total_pages=result["total_pages"],
            debit_sum=result["debit_sum"],
            credit_sum=result["credit_sum"],
            parsed_filters=SmartSearchFilters(is_smart_search=False),
            search_type="fuzzy"
        )

    # Smart search - parse natural language
    parsed_filters = await parse_natural_language_query(request.query, categories)

    # Convert category names to IDs
    category_ids = None
    if parsed_filters.categories:
        category_ids = await _get_category_ids_by_names(db, parsed_filters.categories)

    # Execute filtered query
    result = await get_filtered_transactions(
        db=db,
        page=request.page,
        limit=request.limit,
        start_date=parsed_filters.date_from,
        end_date=parsed_filters.date_to,
        payment_type=parsed_filters.payment_type,
        sort_by=request.sort_by,
        sort_order=request.sort_order,
        category_ids=category_ids if category_ids else None,
        amount_min=parsed_filters.amount_min,
        amount_max=parsed_filters.amount_max,
        merchant_pattern=parsed_filters.merchant_pattern
    )

    return SmartSearchResponse(
        data=result["data"],
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        total_pages=result["total_pages"],
        debit_sum=result["debit_sum"],
        credit_sum=result["credit_sum"],
        parsed_filters=parsed_filters,
        search_type="smart"
    )
