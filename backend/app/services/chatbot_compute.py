"""
Modular computation functions for the chatbot service.

These functions provide reusable financial aggregations and projections
that can be called by the chatbot operation handlers.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from .. import models
from .rules import get_or_create_settings


async def _get_settings_context(db: AsyncSession) -> Dict[str, Any]:
    """Get user settings for filtering transactions."""
    settings = await get_or_create_settings(db)
    ignored_cats = [x.strip() for x in settings.ignored_categories.split(',')] if settings.ignored_categories else []
    income_cats = [x.strip() for x in settings.income_categories.split(',')] if settings.income_categories else []
    return {
        "ignored_categories": ignored_cats,
        "income_categories": income_cats,
        "budget_type": settings.budget_type,
        "budget_value": float(settings.budget_value),
        "salary_day": settings.salary_day,
    }


async def _fetch_transactions_for_period(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    category_name: Optional[str] = None,
    merchant_pattern: Optional[str] = None,
    payment_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch transactions for a given period with optional filters.

    Returns list of dicts with: amount, txn_date, payment_type, category_name, merchant
    """
    stmt = (
        select(
            models.Transaction.amount,
            models.Transaction.txn_date,
            models.Transaction.payment_type,
            models.Transaction.merchant_name,
            models.Category.name.label("category_name")
        )
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.txn_date >= start_date)
        .where(models.Transaction.txn_date <= end_date)
    )

    if category_name:
        stmt = stmt.where(models.Category.name.ilike(f"%{category_name}%"))

    if merchant_pattern:
        stmt = stmt.where(models.Transaction.merchant_name.ilike(f"%{merchant_pattern}%"))

    if payment_type:
        stmt = stmt.where(models.Transaction.payment_type == payment_type.upper())

    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.fetchall()]


def _calculate_date_range(
    months_back: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    relative: Optional[str] = None,
) -> Tuple[date, date]:
    """
    Calculate start and end dates based on various input types.

    relative options: "last_week", "this_week", "last_month", "this_month",
                     "last_3_months", "last_6_months", "last_year"
    """
    today = date.today()

    if relative:
        relative_lower = relative.lower().replace(" ", "_")
        if relative_lower in ("last_week", "past_week"):
            return today - timedelta(days=7), today
        elif relative_lower in ("this_week",):
            # Monday of this week
            start = today - timedelta(days=today.weekday())
            return start, today
        elif relative_lower in ("last_month", "past_month"):
            return today - timedelta(days=30), today
        elif relative_lower == "this_month":
            return today.replace(day=1), today
        elif relative_lower in ("last_3_months", "past_3_months"):
            return today - timedelta(days=90), today
        elif relative_lower in ("last_6_months", "past_6_months"):
            return today - timedelta(days=180), today
        elif relative_lower in ("last_year", "past_year"):
            return today - timedelta(days=365), today

    if months_back:
        return today - timedelta(days=months_back * 30), today

    if start_date and end_date:
        return start_date, end_date

    if start_date:
        return start_date, today

    if end_date:
        return today - timedelta(days=30), end_date

    # Default: last 30 days
    return today - timedelta(days=30), today


async def get_avg_spending_by_category(
    db: AsyncSession,
    category_name: Optional[str] = None,
    months_back: int = 3,
) -> Dict[str, Any]:
    """
    Calculate average monthly spending per category.

    Args:
        db: Database session
        category_name: Optional specific category to query (fuzzy match)
        months_back: Number of months to average over (default 3)

    Returns:
        Dict with avg_monthly_total and per-category averages
    """
    settings = await _get_settings_context(db)
    start_date, end_date = _calculate_date_range(months_back=months_back)

    transactions = await _fetch_transactions_for_period(db, start_date, end_date)

    # Group by month and category
    monthly_category_spend = defaultdict(lambda: defaultdict(float))
    monthly_total = defaultdict(float)

    for txn in transactions:
        cat_name = txn["category_name"]

        # Skip ignored and income categories
        if cat_name in settings["ignored_categories"]:
            continue
        if cat_name in settings["income_categories"]:
            continue

        p_type = (txn["payment_type"] or "").upper()
        if p_type != "DEBIT":
            continue

        month_key = f"{txn['txn_date'].year}-{txn['txn_date'].month:02d}"
        amount = float(txn["amount"])

        monthly_category_spend[month_key][cat_name] += amount
        monthly_total[month_key] += amount

    num_months = max(len(monthly_total), 1)

    # Calculate averages
    category_totals = defaultdict(float)
    for month_data in monthly_category_spend.values():
        for cat, amount in month_data.items():
            category_totals[cat] += amount

    avg_by_category = {cat: round(total / num_months, 2) for cat, total in category_totals.items()}
    avg_monthly_total = round(sum(monthly_total.values()) / num_months, 2)

    result = {
        "months_analyzed": num_months,
        "avg_monthly_total": avg_monthly_total,
        "avg_by_category": avg_by_category,
        "period": {"start": str(start_date), "end": str(end_date)},
    }

    # If specific category requested, extract it
    if category_name:
        matched_cat = None
        matched_avg = 0
        for cat, avg in avg_by_category.items():
            if category_name.lower() in cat.lower():
                matched_cat = cat
                matched_avg = avg
                break
        result["requested_category"] = {
            "name": matched_cat or category_name,
            "avg_monthly": matched_avg,
            "found": matched_cat is not None,
        }

    return result


async def get_avg_transaction_amount(
    db: AsyncSession,
    category_name: Optional[str] = None,
    merchant_pattern: Optional[str] = None,
    payment_type: Optional[str] = None,
    months_back: int = 3,
) -> Dict[str, Any]:
    """
    Calculate average transaction amount with optional filters.

    Returns avg, min, max, count of matching transactions.
    """
    start_date, end_date = _calculate_date_range(months_back=months_back)

    transactions = await _fetch_transactions_for_period(
        db, start_date, end_date,
        category_name=category_name,
        merchant_pattern=merchant_pattern,
        payment_type=payment_type,
    )

    if not transactions:
        return {
            "count": 0,
            "avg_amount": 0,
            "min_amount": 0,
            "max_amount": 0,
            "total": 0,
            "period": {"start": str(start_date), "end": str(end_date)},
        }

    amounts = [float(txn["amount"]) for txn in transactions]

    return {
        "count": len(amounts),
        "avg_amount": round(sum(amounts) / len(amounts), 2),
        "min_amount": round(min(amounts), 2),
        "max_amount": round(max(amounts), 2),
        "total": round(sum(amounts), 2),
        "period": {"start": str(start_date), "end": str(end_date)},
    }


async def get_spending_velocity(
    db: AsyncSession,
    window_days: int = 7,
) -> Dict[str, Any]:
    """
    Calculate rate of spending change comparing current window to previous window.

    Returns current/previous window spending and percentage change.
    """
    settings = await _get_settings_context(db)
    today = date.today()

    # Current window
    current_start = today - timedelta(days=window_days)
    current_txns = await _fetch_transactions_for_period(db, current_start, today)

    # Previous window
    prev_start = current_start - timedelta(days=window_days)
    prev_end = current_start - timedelta(days=1)
    prev_txns = await _fetch_transactions_for_period(db, prev_start, prev_end)

    def sum_debits(txns):
        total = 0.0
        for txn in txns:
            if txn["category_name"] in settings["ignored_categories"]:
                continue
            if txn["category_name"] in settings["income_categories"]:
                continue
            if (txn["payment_type"] or "").upper() == "DEBIT":
                total += float(txn["amount"])
        return total

    current_spend = sum_debits(current_txns)
    prev_spend = sum_debits(prev_txns)

    if prev_spend > 0:
        change_percent = ((current_spend - prev_spend) / prev_spend) * 100
    elif current_spend > 0:
        change_percent = 100.0  # Went from 0 to something
    else:
        change_percent = 0.0

    # Determine velocity status
    if change_percent > 20:
        status = "increasing_fast"
    elif change_percent > 5:
        status = "increasing"
    elif change_percent < -20:
        status = "decreasing_fast"
    elif change_percent < -5:
        status = "decreasing"
    else:
        status = "stable"

    return {
        "window_days": window_days,
        "current_window": {
            "start": str(current_start),
            "end": str(today),
            "spending": round(current_spend, 2),
        },
        "previous_window": {
            "start": str(prev_start),
            "end": str(prev_end),
            "spending": round(prev_spend, 2),
        },
        "change_percent": round(change_percent, 1),
        "status": status,
    }


async def get_category_breakdown_for_period(
    db: AsyncSession,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    months_back: Optional[int] = None,
    relative: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get category breakdown (spending by category) for a date range.
    """
    settings = await _get_settings_context(db)
    start, end = _calculate_date_range(
        months_back=months_back,
        start_date=start_date,
        end_date=end_date,
        relative=relative,
    )

    transactions = await _fetch_transactions_for_period(db, start, end)

    category_totals = defaultdict(float)
    total_spend = 0.0

    for txn in transactions:
        cat_name = txn["category_name"]

        if cat_name in settings["ignored_categories"]:
            continue
        if cat_name in settings["income_categories"]:
            continue
        if (txn["payment_type"] or "").upper() != "DEBIT":
            continue

        amount = float(txn["amount"])
        category_totals[cat_name] += amount
        total_spend += amount

    # Sort by amount descending
    breakdown = [
        {
            "category": cat,
            "amount": round(amt, 2),
            "percentage": round((amt / total_spend) * 100, 1) if total_spend > 0 else 0,
        }
        for cat, amt in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "period": {"start": str(start), "end": str(end)},
        "total_spend": round(total_spend, 2),
        "breakdown": breakdown,
    }


async def calculate_time_range_spend(
    db: AsyncSession,
    category_name: Optional[str] = None,
    months_back: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    relative: Optional[str] = None,
    payment_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate total spending for a flexible time range with optional filters.

    This is the primary function for "How much have I spent on X in Y period?" queries.
    """
    settings = await _get_settings_context(db)
    start, end = _calculate_date_range(
        months_back=months_back,
        start_date=start_date,
        end_date=end_date,
        relative=relative,
    )

    transactions = await _fetch_transactions_for_period(
        db, start, end,
        category_name=category_name,
        payment_type=payment_type,
    )

    total = 0.0
    count = 0
    category_totals = defaultdict(float)

    for txn in transactions:
        cat_name = txn["category_name"]

        # Skip ignored categories (but not income if explicitly filtering for CREDIT)
        if cat_name in settings["ignored_categories"]:
            continue

        # If no payment_type filter and it's income category with DEBIT, skip
        if not payment_type and cat_name in settings["income_categories"]:
            if (txn["payment_type"] or "").upper() != "CREDIT":
                continue

        amount = float(txn["amount"])
        total += amount
        count += 1
        category_totals[cat_name] += amount

    # Determine the primary category if filtering
    primary_category = None
    if category_name:
        for cat in category_totals:
            if category_name.lower() in cat.lower():
                primary_category = cat
                break

    return {
        "period": {"start": str(start), "end": str(end)},
        "total": round(total, 2),
        "transaction_count": count,
        "category_filter": category_name,
        "matched_category": primary_category,
        "payment_type_filter": payment_type,
        "breakdown_by_category": {cat: round(amt, 2) for cat, amt in category_totals.items()},
    }


async def project_future_spending(
    db: AsyncSession,
    months_forward: int,
    adjustments: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Project future spending and savings over multiple months.

    Args:
        db: Database session
        months_forward: Number of months to project
        adjustments: Dict of category -> monthly change (negative for reductions)
                    e.g., {"Food": -10000} means reduce food by 10k/month

    Returns:
        Projected monthly surpluses and total accumulated savings
    """
    from .chatbot import _get_historical_averages

    historical = await _get_historical_averages(db, months_back=3)
    adjustments = adjustments or {}

    avg_budget = historical["avg_monthly_budget"]
    avg_spend = historical["avg_monthly_spend"]
    avg_category_spend = historical["avg_category_spend"]
    current_surplus = historical["avg_monthly_surplus"]

    # Calculate additional savings from adjustments
    additional_monthly_savings = 0.0
    adjustment_details = {}

    for cat_name, change in adjustments.items():
        # Find matching category (fuzzy match)
        matched_cat = None
        current_spend = 0

        for existing_cat, spend in avg_category_spend.items():
            if cat_name.lower() in existing_cat.lower() or existing_cat.lower() in cat_name.lower():
                matched_cat = existing_cat
                current_spend = spend
                break

        # Change is negative for reductions
        reduction = abs(change) if change < 0 else 0

        if matched_cat:
            # Can't save more than you spend
            actual_savings = min(reduction, current_spend)
            new_spend = current_spend - actual_savings
        else:
            # Category not found, but still count intended reduction
            actual_savings = reduction
            new_spend = 0

        additional_monthly_savings += actual_savings
        adjustment_details[matched_cat or cat_name] = {
            "current_avg_spend": current_spend,
            "intended_reduction": reduction,
            "actual_savings": actual_savings,
            "new_avg_spend": new_spend,
        }

    # Calculate projections
    new_monthly_surplus = current_surplus + additional_monthly_savings

    monthly_projections = []
    accumulated = 0.0

    for month_num in range(1, months_forward + 1):
        accumulated += new_monthly_surplus
        monthly_projections.append({
            "month": month_num,
            "surplus": round(new_monthly_surplus, 2),
            "accumulated_savings": round(accumulated, 2),
        })

    return {
        "months_projected": months_forward,
        "historical_context": {
            "avg_monthly_budget": avg_budget,
            "avg_monthly_spend": avg_spend,
            "current_monthly_surplus": current_surplus,
        },
        "adjustments": adjustment_details,
        "additional_monthly_savings": round(additional_monthly_savings, 2),
        "new_monthly_surplus": round(new_monthly_surplus, 2),
        "total_projected_savings": round(accumulated, 2),
        "monthly_projections": monthly_projections,
    }


async def calculate_goal_plan(
    db: AsyncSession,
    target_amount: float,
    target_months: Optional[int] = None,
    goal_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a plan to reach a savings goal.

    If target_months is provided, calculates required monthly savings.
    If not provided, calculates months needed at current rate.

    Returns plan with feasibility analysis and suggestions.
    """
    from .chatbot import _get_historical_averages

    historical = await _get_historical_averages(db, months_back=3)

    current_surplus = historical["avg_monthly_surplus"]
    avg_spend = historical["avg_monthly_spend"]
    avg_category_spend = historical["avg_category_spend"]

    result = {
        "target_amount": target_amount,
        "goal_name": goal_name,
        "current_monthly_surplus": current_surplus,
    }

    if target_months:
        # Calculate required monthly savings
        required_monthly = target_amount / target_months
        shortfall = required_monthly - current_surplus

        result["target_months"] = target_months
        result["required_monthly_savings"] = round(required_monthly, 2)
        result["shortfall_per_month"] = round(max(0, shortfall), 2)
        result["is_feasible"] = shortfall <= 0

        if shortfall > 0:
            # Suggest categories to cut
            sorted_cats = sorted(
                avg_category_spend.items(),
                key=lambda x: x[1],
                reverse=True
            )

            suggestions = []
            remaining_shortfall = shortfall

            for cat, spend in sorted_cats:
                if remaining_shortfall <= 0:
                    break
                # Suggest cutting up to 30% of category spend
                max_cut = spend * 0.3
                suggested_cut = min(max_cut, remaining_shortfall)

                if suggested_cut >= 100:  # Only suggest meaningful cuts
                    suggestions.append({
                        "category": cat,
                        "current_spend": round(spend, 2),
                        "suggested_reduction": round(suggested_cut, 2),
                        "new_spend": round(spend - suggested_cut, 2),
                    })
                    remaining_shortfall -= suggested_cut

            result["suggestions"] = suggestions
            result["achievable_with_cuts"] = remaining_shortfall <= 0
    else:
        # Calculate months needed at current rate
        if current_surplus <= 0:
            result["months_needed"] = None
            result["is_feasible"] = False
            result["reason"] = "No monthly surplus - you're spending more than your budget"
        else:
            months_needed = target_amount / current_surplus
            result["months_needed"] = round(months_needed, 1)
            result["is_feasible"] = True

            # Calculate if they increase savings by 20%
            faster_surplus = current_surplus * 1.2
            faster_months = target_amount / faster_surplus
            result["faster_option"] = {
                "increase_savings_by_percent": 20,
                "months_needed": round(faster_months, 1),
            }

    return result


async def forecast_budget_status(
    db: AsyncSession,
    days_forward: int = 0,
) -> Dict[str, Any]:
    """
    Forecast whether user will stay under budget for the current cycle.

    Uses spending velocity and remaining days to project end-of-cycle status.

    Args:
        days_forward: Days to project (0 = end of current cycle)
    """
    from .analytics import calculate_financial_health
    from .rules import get_or_create_settings

    settings = await get_or_create_settings(db)
    health = await calculate_financial_health(db, offset=0)
    velocity = await get_spending_velocity(db, window_days=7)

    total_budget = health["total_budget"]
    current_spend = health["total_spend"]
    days_left = health["days_left"]
    remaining = health["budget_remaining"]

    # Use days_left if days_forward is 0
    projection_days = days_forward if days_forward > 0 else days_left

    # Calculate daily spend rate from recent velocity
    current_daily_rate = velocity["current_window"]["spending"] / velocity["window_days"]

    # Project future spending
    projected_additional = current_daily_rate * projection_days
    projected_total = current_spend + projected_additional
    projected_remaining = total_budget - projected_total

    # Determine status
    if projected_remaining >= 0:
        if projected_remaining > total_budget * 0.2:
            status = "well_under_budget"
            message = f"You're on track to end the cycle with ₹{projected_remaining:,.0f} remaining."
        elif projected_remaining > 0:
            status = "under_budget"
            message = f"You'll likely stay under budget with ₹{projected_remaining:,.0f} to spare."
        else:
            status = "on_budget"
            message = "You're projected to hit exactly your budget."
    else:
        overspend = abs(projected_remaining)
        status = "over_budget"
        message = f"At current rate, you'll overspend by ₹{overspend:,.0f}."

    # Calculate required daily spend to stay on budget
    safe_daily = remaining / projection_days if projection_days > 0 else 0

    return {
        "current_budget": total_budget,
        "current_spend": current_spend,
        "current_remaining": remaining,
        "days_left_in_cycle": days_left,
        "projection_days": projection_days,
        "current_daily_rate": round(current_daily_rate, 2),
        "safe_daily_spend": round(safe_daily, 2),
        "spending_velocity_status": velocity["status"],
        "projected_total_spend": round(projected_total, 2),
        "projected_remaining": round(projected_remaining, 2),
        "status": status,
        "message": message,
        "will_stay_under_budget": projected_remaining >= 0,
    }
