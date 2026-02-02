import holidays
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from .. import models, schemas
from .rules import get_or_create_settings

def get_adjusted_payday(year: int, month: int, salary_day: int) -> date:
    """Adjusts the salary day if it falls on a weekend."""
    try:
        base_date = date(year, month, salary_day)
    except ValueError:
        if month == 12: base_date = date(year + 1, 1, 1) - timedelta(days=1)
        else: base_date = date(year, month + 1, 1) - timedelta(days=1)

    weekday = base_date.weekday()
    if weekday == 5: return base_date - timedelta(days=1)
    elif weekday == 6: return base_date - timedelta(days=2)
    return base_date

def get_theoretical_cycle_dates(salary_day: int, offset: int):
    """Calculates standard Start/End dates based on offset."""
    today = date.today()
    this_month_payday = get_adjusted_payday(today.year, today.month, salary_day)
    
    if today >= this_month_payday:
        anchor_month, anchor_year = today.month, today.year
    else:
        anchor_month = 12 if today.month == 1 else today.month - 1
        anchor_year = today.year - 1 if today.month == 1 else today.year

    total_months_linear = (anchor_year * 12) + (anchor_month - 1)
    target_total_months = total_months_linear - offset
    
    target_year = target_total_months // 12
    target_month = (target_total_months % 12) + 1
    
    start_date = get_adjusted_payday(target_year, target_month, salary_day)
    
    next_total = target_total_months + 1
    next_y, next_m = next_total // 12, (next_total % 12) + 1
    next_start = get_adjusted_payday(next_y, next_m, salary_day)
    end_date = next_start - timedelta(days=1)
    
    return start_date, end_date

# 🔒 SECURE LOGIC: PREVENT DOUBLE SALARY
async def get_secure_cycle_dates(db: AsyncSession, salary_day: int, offset: int, income_list: list):
    """
    1. Calculates theoretical dates.
    2. Scans the last few days of the cycle for an 'Early Salary'.
    3. If found, snaps the end_date to prevent double counting.
    """
    start_date, end_date = get_theoretical_cycle_dates(salary_day, offset)
    
    if not income_list:
        return start_date, end_date

    # Look for 'Early Salary' in the last 10 days of the cycle
    # (e.g., If cycle ends 25th, check 15th to 25th for a Credit in Income Categories)
    scan_start = end_date - timedelta(days=10)
    
    stmt = (
        select(models.Transaction.txn_date)
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(
            models.Transaction.txn_date >= scan_start,
            models.Transaction.txn_date <= end_date,
            models.Transaction.payment_type == 'credit',
            models.Category.name.in_(income_list)
        )
        .order_by(models.Transaction.txn_date.asc()) # Find the FIRST occurrence in the danger zone
        .limit(1)
    )
    
    result = await db.execute(stmt)
    early_salary_date = result.scalar_one_or_none()

    if early_salary_date:
        # 🚨 Early Salary Detected!
        # If we find a salary on the 24th, and our cycle ends on the 25th,
        # we MUST end our cycle on the 23rd to push that salary to the next cycle.
        print(f"[CYCLE FIX] Early salary detected on {early_salary_date}. Snapping end date.")
        
        # Ensure we don't snap if the salary is actually the START of the current cycle (edge case for short cycles)
        if early_salary_date > start_date + timedelta(days=5):
            end_date = early_salary_date - timedelta(days=1)

    return start_date, end_date
# ==========================================
# 1. DATA FETCHING HELPERS
# ==========================================

async def _fetch_cycle_transactions(
    db: AsyncSession, 
    start_date: date, 
    end_date: date
) -> List[Any]:
    """Fetches all transactions within a specific date range."""
    stmt = (
        select(
            models.Transaction.amount, 
            models.Transaction.txn_date, 
            models.Transaction.payment_type,
            models.Transaction.merchant_name, 
            models.Category.name.label("category_name"), 
            models.Category.color.label("category_color")
        )
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.txn_date >= start_date, models.Transaction.txn_date <= end_date)
        .order_by(models.Transaction.txn_date.asc())
    )
    result = await db.execute(stmt)
    return result.mappings().all()

async def _fetch_recent_transactions(
    db: AsyncSession, 
    start_date: date, 
    end_date: date, 
    limit: int = 5
) -> List[Any]:
    """Fetches the N most recent transactions for the dashboard list."""
    stmt = (
        select(
            models.Transaction.id, models.Transaction.amount, models.Transaction.txn_date, 
            models.Transaction.payment_type, models.Transaction.merchant_name, models.Transaction.payment_mode, 
            models.Transaction.bank_name, models.Category.name.label("category_name"), models.Category.color.label("category_color")
        )
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.txn_date >= start_date, models.Transaction.txn_date <= end_date)
        .order_by(models.Transaction.txn_date.desc()).limit(limit)
    )
    result = await db.execute(stmt)
    return result.mappings().all()

async def _fetch_fallback_income(
    db: AsyncSession, 
    start_date: date, 
    income_categories: List[str]
) -> float:
    """Looks back 7 days prior to cycle start to find income if none exists in current cycle."""
    lookback_stmt = (
        select(models.Transaction.amount)
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(
            models.Transaction.txn_date >= start_date - timedelta(days=7),
            models.Transaction.txn_date < start_date,
            func.lower(models.Transaction.payment_type) == 'credit',
            models.Category.name.in_(income_categories)
        )
        .order_by(models.Transaction.txn_date.desc())
        .limit(1)
    )
    return float(await db.scalar(lookback_stmt) or 0.0)

# ==========================================
# 2. DATA PROCESSING HELPERS
# ==========================================

def _process_transaction_aggregates(
    transactions: List[Any], 
    cycle_start: date,
    ignored_cats: List[str], 
    income_cats: List[str]
) -> Tuple[float, float, Dict[str, Any], Dict[int, float]]:
    """
    Iterates through transactions to calculate totals, categorize spending, 
    and build daily trend data.
    Returns: (total_spend, total_income, category_map, daily_trend_map)
    """
    total_spend = 0.0
    total_income = 0.0
    category_map = {}
    daily_trend = {}

    for txn in transactions:
        amount = float(txn.amount)
        p_type = txn.payment_type.upper() if txn.payment_type else "UNKNOWN"
        cat_name = txn.category_name

        if cat_name in ignored_cats: 
            continue
        
        # Handle Income
        if cat_name in income_cats:
            if p_type == "CREDIT": total_income += amount
            elif p_type == "DEBIT": total_income -= amount
            continue

        # Handle Expense Logic (Debit adds to spend, Credit reduces spend)
        day_idx = (txn.txn_date - cycle_start).days + 1
        
        if p_type == "DEBIT":
            total_spend += amount
            
            # Update Category Map
            if cat_name not in category_map: 
                category_map[cat_name] = {"value": 0.0, "color": txn.category_color}
            category_map[cat_name]["value"] += amount
            
            # Update Trend
            daily_trend[day_idx] = daily_trend.get(day_idx, 0) + amount

        elif p_type == "CREDIT":
            total_spend -= amount
            if cat_name in category_map: 
                category_map[cat_name]["value"] -= amount
            daily_trend[day_idx] = daily_trend.get(day_idx, 0) - amount

    return total_spend, total_income, category_map, daily_trend

def _calculate_previous_spend_todate(
    prev_transactions: List[Any],
    prev_start: date,
    days_passed_current: int,
    ignored_cats: List[str],
    income_cats: List[str]
) -> Tuple[float, Dict[int, float]]:
    """
    Calculates the total spend of the previous cycle UP TO the same day 
    as the current cycle (for accurate comparison).
    """
    prev_trend = {}
    spend_upto_now = 0.0

    for txn in prev_transactions:
        if txn.category_name in ignored_cats or txn.category_name in income_cats:
            continue

        amount = float(txn.amount)
        p_type = txn.payment_type.upper() if txn.payment_type else "UNKNOWN"
        day_idx = (txn.txn_date - prev_start).days + 1
        
        val = amount if p_type == "DEBIT" else -amount
        prev_trend[day_idx] = prev_trend.get(day_idx, 0) + val

        if day_idx <= days_passed_current:
            spend_upto_now += val
            
    return spend_upto_now, prev_trend

# ==========================================
# 3. GRAPH & UI BUILDERS
# ==========================================

def _calculate_burn_rate_status(
    total_spend: float,
    budget_limit: float,
    days_passed: int,
    days_in_cycle: int
) -> str:
    """
    Calculate burn rate status based on budget used vs time passed.
    Returns: 'Over Budget', 'High Burn', 'Caution', or 'On Track'
    """
    if budget_limit <= 0:
        return "On Track"

    budget_remaining = budget_limit - total_spend
    if budget_remaining < 0:
        return "Over Budget"

    if days_in_cycle <= 0 or days_passed <= 0:
        return "On Track"

    budget_used_pct = (total_spend / budget_limit) * 100
    time_passed_pct = (days_passed / days_in_cycle) * 100

    if budget_used_pct > time_passed_pct + 15:
        return "High Burn"
    elif budget_used_pct > time_passed_pct + 5:
        return "Caution"
    return "On Track"


def _build_trend_graph(
    start_date: date,
    days_in_cycle: int,
    days_passed: int,
    prev_duration: int,
    curr_trend_data: Dict[int, float],
    prev_trend_data: Dict[int, float],
    budget_limit: float,
    offset: int
) -> List[Dict[str, Any]]:
    """Generates the list of data points for the frontend Line/Area chart."""
    trend_list = []
    max_days = max(days_in_cycle, prev_duration) if days_in_cycle > 0 or prev_duration > 0 else 1
    ideal_daily = budget_limit / days_in_cycle if days_in_cycle > 0 else 0
    
    cum_actual = 0.0
    cum_prev = 0.0

    for i in range(1, max_days + 1):
        # Determine visibility logic
        show_actual = (i <= days_in_cycle)
        if offset == 0 and i > days_passed: 
            show_actual = False
            
        cum_actual += curr_trend_data.get(i, 0.0)
        cum_prev += prev_trend_data.get(i, 0.0)
        
        current_trend_date = start_date + timedelta(days=i-1)
        
        trend_list.append({
            "day": i,
            "date": current_trend_date.strftime("%d %b"),
            "actual": cum_actual if show_actual else None,
            "previous": cum_prev if i <= prev_duration else None,
            "ideal": round(ideal_daily * i, 2) if i <= days_in_cycle else None
        })
    return trend_list

# ==========================================
# 4. MAIN ORCHESTRATOR
# ==========================================

async def calculate_financial_health(db: AsyncSession, offset: int = 0):
    settings = await get_or_create_settings(db)
    
    # 0. Configuration
    ignored = [x.strip() for x in settings.ignored_categories.split(',')] if settings.ignored_categories else []
    income_cats = [x.strip() for x in settings.income_categories.split(',')] if settings.income_categories else []

    # 1. Date Calculation
    start, end = await get_secure_cycle_dates(db, settings.salary_day, offset, income_cats)
    p_start, p_end = await get_secure_cycle_dates(db, settings.salary_day, offset + 1, income_cats)

    # 2. Fetching
    curr_txns = await _fetch_cycle_transactions(db, start, end)
    prev_txns = await _fetch_cycle_transactions(db, p_start, p_end)
    recent_txns = await _fetch_recent_transactions(db, start, end)

    # 3. Processing Current Cycle
    total_spend, total_income, cat_map, curr_trend = _process_transaction_aggregates(
        curr_txns, start, ignored, income_cats
    )

    # 4. Processing Previous Cycle (for comparison)
    days_in_cycle = (end - start).days + 1
    today = date.today()
    
    # Calculate how many days have passed in the current view
    if offset > 0:
        days_passed = days_in_cycle
    else:
        days_passed = max(0, min((today - start).days + 1, days_in_cycle))
        
    prev_spend_upto_now, prev_trend = _calculate_previous_spend_todate(
        prev_txns, p_start, days_passed, ignored, income_cats
    )

    # 5. Budget Logic & Fallback Income
    calc_income = total_income
    if settings.budget_type == "PERCENTAGE" and calc_income == 0:
        calc_income = await _fetch_fallback_income(db, start, income_cats)

    budget_limit = float(settings.budget_value)
    if settings.budget_type == "PERCENTAGE":
        budget_limit = (calc_income * settings.budget_value) / 100

    # 6. Final Metrics
    budget_remaining = budget_limit - total_spend
    days_left = max(0, days_in_cycle - days_passed)
    safe_daily = budget_remaining / days_left if days_left > 0 and budget_remaining > 0 else 0.0

    # Calculate burn rate status
    burn_rate_status = _calculate_burn_rate_status(
        total_spend, budget_limit, days_passed, days_in_cycle
    )

    # Compare vs Previous
    if prev_spend_upto_now > 0:
        diff_percent = ((total_spend - prev_spend_upto_now) / prev_spend_upto_now) * 100
    else:
        diff_percent = 100.0 if total_spend > 0 else 0.0

    # 7. Construct View Objects
    trend_graph = _build_trend_graph(
        start, days_in_cycle, days_passed, 
        (p_end - p_start).days + 1, 
        curr_trend, prev_trend, budget_limit, offset
    )

    cat_breakdown = [
        {"name": k, "value": v["value"], "color": v["color"]} 
        for k, v in cat_map.items() if v["value"] > 0
    ]
    cat_breakdown.sort(key=lambda x: x["value"], reverse=True)

    return {
        "cycle_start": start,
        "cycle_end": end,
        "days_in_cycle": days_in_cycle,
        "days_passed": days_passed,
        "days_left": days_left,
        "total_budget": round(budget_limit, 2),
        "total_spend": round(total_spend, 2),
        "budget_remaining": round(budget_remaining, 2),
        "safe_to_spend_daily": round(safe_daily, 2),
        "burn_rate_status": burn_rate_status,
        "projected_spend": round((total_spend / days_passed) * days_in_cycle if days_passed > 0 and days_in_cycle > 0 else 0, 2),
        "prev_cycle_spend_todate": round(prev_spend_upto_now, 2),
        "spend_diff_percent": round(diff_percent, 1),
        "recent_transactions": recent_txns,
        "category_breakdown": cat_breakdown,
        "spending_trend": trend_graph,
        "view_mode": "Current" if offset == 0 else f"History (-{offset})"
    }