import holidays
from datetime import date, timedelta
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
# 📊 CORE LOGIC
# ==========================================
async def calculate_financial_health(db: AsyncSession, offset: int = 0):
    settings = await get_or_create_settings(db)
    ignored_list = [x.strip() for x in settings.ignored_categories.split(',') if x.strip()] if settings.ignored_categories else []
    income_list = [x.strip() for x in settings.income_categories.split(',') if x.strip()] if settings.income_categories else []

    # 1. Get SECURE Dates (Applies the cut-off logic)
    start_date, end_date = await get_secure_cycle_dates(db, settings.salary_day, offset, income_list)
    prev_start_date, prev_end_date = await get_secure_cycle_dates(db, settings.salary_day, offset + 1, income_list)

    print(f"[DEBUG] Computed Cycle: {start_date} -> {end_date}")

    # 2. Fetch Transactions (Using new secure dates)
    stmt = (
        select(
            models.Transaction.amount, models.Transaction.txn_date, models.Transaction.payment_type,
            models.Transaction.merchant_name, models.Category.name.label("category_name"), models.Category.color.label("category_color")
        )
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.txn_date >= start_date, models.Transaction.txn_date <= end_date)
        .order_by(models.Transaction.txn_date.asc())
    )
    result = await db.execute(stmt)
    transactions = result.mappings().all()

    # 3. Fetch Previous (Using new secure dates)
    stmt_prev = (
        select(models.Transaction.amount, models.Transaction.txn_date, models.Transaction.payment_type, models.Category.name.label("category_name"))
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.txn_date >= prev_start_date, models.Transaction.txn_date <= prev_end_date)
    )
    result_prev = await db.execute(stmt_prev)
    prev_transactions = result_prev.mappings().all()

    # 4. Process Current Data
    total_spend = 0.0
    total_income = 0.0
    category_map = {}
    spending_trend_data = {} 
    
    for txn in transactions:
        amount = float(txn.amount)
        p_type = txn.payment_type.upper() if txn.payment_type else "UNKNOWN"
        cat_name = txn.category_name

        if cat_name in ignored_list: continue
        
        # Calculate Income
        if cat_name in income_list:
            if p_type == "CREDIT": total_income += amount
            elif p_type == "DEBIT": total_income -= amount
            continue

        if p_type == "DEBIT":
            total_spend += amount
            if cat_name not in category_map: category_map[cat_name] = {"value": 0.0, "color": txn.category_color}
            category_map[cat_name]["value"] += amount
            
            day_idx = (txn.txn_date - start_date).days + 1
            spending_trend_data[day_idx] = spending_trend_data.get(day_idx, 0) + amount

        elif p_type == "CREDIT":
            total_spend -= amount
            if cat_name in category_map: category_map[cat_name]["value"] -= amount
            day_idx = (txn.txn_date - start_date).days + 1
            spending_trend_data[day_idx] = spending_trend_data.get(day_idx, 0) - amount

    # 5. Process Previous Data
    days_in_cycle = (end_date - start_date).days + 1
    today = date.today()
    
    if offset > 0:
        days_passed = days_in_cycle
    else:
        days_passed = max(0, min((today - start_date).days, days_in_cycle))
        
    days_left = max(0, days_in_cycle - days_passed)

    prev_trend_data = {}
    prev_spend_upto_now = 0.0
    
    for txn in prev_transactions:
        p_type = txn.payment_type.upper() if txn.payment_type else "UNKNOWN"
        cat_name = txn.category_name
        if cat_name in ignored_list or cat_name in income_list: continue
        
        amount = float(txn.amount)
        day_idx = (txn.txn_date - prev_start_date).days + 1
        val = amount if p_type == "DEBIT" else -amount
        
        prev_trend_data[day_idx] = prev_trend_data.get(day_idx, 0) + val
        
        if day_idx <= days_passed:
            prev_spend_upto_now += val

    # 6. Fallback Logic: Zero Income Detection
    # If standard Total Income is 0 (maybe salary came BEFORE the cycle start date), look back 7 days.
    calc_income_base = total_income
    
    if settings.budget_type == "PERCENTAGE" and calc_income_base == 0:
        lookback_stmt = (
            select(models.Transaction.amount)
            .join(models.Category, models.Transaction.category_id == models.Category.id)
            .where(
                models.Transaction.txn_date >= start_date - timedelta(days=7),
                models.Transaction.txn_date < start_date,
                models.Transaction.payment_type == 'credit',
                models.Category.name.in_(income_list)
            )
            .order_by(models.Transaction.txn_date.desc())
            .limit(1)
        )
        row = await db.scalar(lookback_stmt)
        if row:
            calc_income_base = float(row)
            print(f"[DEBUG] Fallback income found: {calc_income_base}")

    # 7. Budget Calculation
    budget_limit = float(settings.budget_value)
    if settings.budget_type == "PERCENTAGE":
        budget_limit = (calc_income_base * settings.budget_value) / 100

    budget_remaining = budget_limit - total_spend
    safe_daily = budget_remaining / days_left if days_left > 0 and budget_remaining > 0 else 0.0

    # 8. Comparison Percent
    spend_diff_percent = 0.0
    if prev_spend_upto_now > 0:
        spend_diff_percent = ((total_spend - prev_spend_upto_now) / prev_spend_upto_now) * 100
    elif total_spend > 0:
        spend_diff_percent = 100.0

    # 9. Graph Building
    trend_list = []
    max_days = max(days_in_cycle, (prev_end_date - prev_start_date).days + 1)
    
    cum_actual = 0.0
    cum_prev = 0.0
    ideal_daily = budget_limit / days_in_cycle if days_in_cycle else 0
    
    for i in range(1, max_days + 1):
        show_actual = True
        if offset == 0 and i > days_passed: show_actual = False
        if i > days_in_cycle: show_actual = False
        
        cum_actual += spending_trend_data.get(i, 0.0)
        cum_prev += prev_trend_data.get(i, 0.0)
        show_prev = i <= (prev_end_date - prev_start_date).days + 1
        
        current_trend_date = start_date + timedelta(days=i-1)
        
        trend_list.append({
            "day": i,
            "date": current_trend_date.strftime("%d %b"),
            "actual": cum_actual if show_actual else None,
            "previous": cum_prev if show_prev else None,
            "ideal": round(ideal_daily * i, 2) if i <= days_in_cycle else None
        })

    # 10. Top Categories
    cat_breakdown = [{"name": k, "value": v["value"], "color": v["color"]} for k, v in category_map.items() if v["value"] > 0]
    cat_breakdown.sort(key=lambda x: x["value"], reverse=True)

    # 11. Recent Transactions
    stmt_recent = (
        select(
            models.Transaction.id, models.Transaction.amount, models.Transaction.txn_date, 
            models.Transaction.payment_type, models.Transaction.merchant_name, models.Transaction.payment_mode, 
            models.Transaction.bank_name, models.Category.name.label("category_name"), models.Category.color.label("category_color")
        )
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.txn_date >= start_date, models.Transaction.txn_date <= end_date)
        .order_by(models.Transaction.txn_date.desc()).limit(5)
    )
    result_recent = await db.execute(stmt_recent)
    recent_transactions = result_recent.mappings().all()

    return {
        "cycle_start": start_date,
        "cycle_end": end_date,
        "days_in_cycle": days_in_cycle,
        "days_passed": days_passed,
        "days_left": days_left,
        "total_budget": round(budget_limit, 2),
        "total_spend": round(total_spend, 2),
        "budget_remaining": round(budget_remaining, 2),
        "safe_to_spend_daily": round(safe_daily, 2),
        "burn_rate_status": "Green", 
        "projected_spend": round((total_spend / days_passed) * days_in_cycle if days_passed > 0 else 0, 2),
        "prev_cycle_spend_todate": round(prev_spend_upto_now, 2),
        "spend_diff_percent": round(spend_diff_percent, 1),
        "recent_transactions": recent_transactions,
        "category_breakdown": cat_breakdown,
        "spending_trend": trend_list,
        "view_mode": "Current" if offset == 0 else f"History (-{offset})"
    }