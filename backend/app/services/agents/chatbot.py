"""Helper functions from the original chatbot service.

These are extracted functions that compute agents need but that
don't belong in the main chatbot_compute module.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ... import models
from ..rules import get_or_create_settings


async def _get_historical_averages(db: AsyncSession, months_back: int = 3) -> Dict[str, Any]:
    """Calculate historical monthly averages for budget planning and projections.

    Returns average monthly income, spend, spend by category, and monthly surplus.

    Args:
        db: Database session
        months_back: Number of months to analyze

    Returns:
        Dict with avg_monthly_income, avg_monthly_spend, avg_monthly_budget,
        avg_monthly_surplus, avg_category_spend, months_of_data, budget_type
    """
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


async def _get_categories(db: AsyncSession) -> list[str]:
    """Fetch all category names from the database."""
    stmt = select(models.Category.name)
    result = await db.execute(stmt)
    return [row[0] for row in result.fetchall()]


async def _get_financial_context(db: AsyncSession) -> Dict[str, Any]:
    """Get aggregated financial context (no raw transaction data)."""
    from ..analytics import calculate_financial_health

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
        return {
            "budget": 0,
            "spent": 0,
            "remaining": 0,
            "days_left": 0,
            "status": "Unknown",
            "top_categories": [],
        }
