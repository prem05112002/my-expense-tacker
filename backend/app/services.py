import sys
import os
import uuid
import holidays
from collections import defaultdict
from rapidfuzz import fuzz
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, update, delete
from typing import Optional, List
from datetime import date, timedelta
from fastapi import BackgroundTasks
from . import models, schemas

# ==========================================
# 🔌 CONNECT TO ETL DIRECTORY
# ==========================================
try:
    current_dir = os.path.dirname(os.path.abspath(__file__)) # /app
    backend_dir = os.path.dirname(current_dir)               # /backend
    project_root = os.path.dirname(backend_dir)              # / (Root)
    
    etl_path = os.path.join(project_root, "Etl") 
    sys.path.append(etl_path)

    from email_service import EmailService
    from config import SOURCE_FOLDER, DEST_FOLDER, NON_TXN_FOLDER

except ImportError as e:
    print(f"❌ Import Error in services.py: {e}")
    EmailService = None
    SOURCE_FOLDER = "sync-expense-tracker"
    DEST_FOLDER = "expenses"
    NON_TXN_FOLDER = "non-transaction"

# ==========================================
# 🛠️ HELPER: MOVE EMAIL IN BACKGROUND
# ==========================================
def move_email_in_background(uid: str, target_folder: str):
    if not EmailService:
        return

    print(f"🔄 [Background] Moving email UID {uid} to '{target_folder}'...")
    try:
        service = EmailService()
        if service.connect():
            service.mail.select(SOURCE_FOLDER) 
            service.move_email(uid.encode('utf-8'), target_folder)
            service.close()
            print(f"✅ [Background] Moved email {uid} successfully.")
    except Exception as e:
        print(f"❌ [Background] Failed to move email {uid}: {e}")

# ==========================================
# ⚙️ SETTINGS & PAYDAY LOGIC
# ==========================================
async def get_or_create_settings(db: AsyncSession):
    stmt = select(models.UserSettings).limit(1)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()
    if not settings:
        settings = models.UserSettings(salary_day=1, budget_type="PERCENTAGE", budget_value=40.0)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings

async def update_settings(db: AsyncSession, data: schemas.UserSettingsUpdate):
    settings = await get_or_create_settings(db)
    settings.salary_day = data.salary_day
    settings.budget_type = data.budget_type
    settings.budget_value = data.budget_value
    if data.ignored_categories is not None: settings.ignored_categories = ",".join(data.ignored_categories)
    else: settings.ignored_categories = ""
    if data.income_categories is not None: settings.income_categories = ",".join(data.income_categories)
    else: settings.income_categories = ""
    settings.view_cycle_offset = data.view_cycle_offset
    await db.commit()
    await db.refresh(settings)
    return settings

def get_adjusted_payday(year: int, month: int, base_day: int) -> date:
    country_holidays = holidays.country_holidays('IN', years=year)
    try:
        target_date = date(year, month, base_day)
    except ValueError:
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        target_date = date(year, month, last_day)

    # Walk backwards if weekend or holiday
    while True:
        is_weekend = target_date.weekday() >= 5
        is_holiday = target_date in country_holidays
        if not is_weekend and not is_holiday:
            return target_date
        target_date -= timedelta(days=1)

# ==========================================
# 🗓️ HELPER: DATE CALCULATIONS
# ==========================================
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

# ==========================================
# 🧠 RULE ENGINE & OTHER SERVICES
# ==========================================
async def preview_rule_changes(db: AsyncSession, pattern: str, match_type: str):
    query = select(models.Transaction)
    if match_type == "CONTAINS":
        query = query.where(models.Transaction.merchant_name.ilike(f"%{pattern}%"))
    elif match_type == "EXACT":
        query = query.where(models.Transaction.merchant_name == pattern)
    query = query.order_by(desc(models.Transaction.txn_date))
    result = await db.execute(query)
    return result.scalars().all()

async def create_rule(db: AsyncSession, rule_data: schemas.RuleCreate):
    rule_dict = rule_data.model_dump(exclude={"excluded_ids"})
    new_rule = models.TransactionRule(**rule_dict)
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    await apply_rule_historical(db, new_rule, rule_data.excluded_ids)
    stmt = select(models.Category).where(models.Category.id == new_rule.category_id)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()
    return {
        **new_rule.__dict__, 
        "category_name": category.name if category else "Uncategorized",
        "category_color": category.color if category else "#cbd5e1"
    }

async def apply_rule_historical(db: AsyncSession, rule: models.TransactionRule, excluded_ids: List[int] = []):
    if rule.match_type == "CONTAINS":
        filter_condition = models.Transaction.merchant_name.ilike(f"%{rule.pattern}%")
    elif rule.match_type == "EXACT":
        filter_condition = (models.Transaction.merchant_name == rule.pattern)
    else:
        return
    stmt = (
        update(models.Transaction)
        .where(filter_condition)
        .values(merchant_name=rule.new_merchant_name, category_id=rule.category_id)
    )
    if excluded_ids:
        stmt = stmt.where(models.Transaction.id.not_in(excluded_ids))
    stmt = stmt.execution_options(synchronize_session=False) 
    await db.execute(stmt)
    await db.commit()

async def get_all_rules(db: AsyncSession):
    stmt = (
        select(models.TransactionRule.id, models.TransactionRule.pattern, models.TransactionRule.new_merchant_name, models.TransactionRule.match_type, models.TransactionRule.category_id, models.Category.name.label("category_name"), models.Category.color.label("category_color"))
        .join(models.Category, models.TransactionRule.category_id == models.Category.id)
    )
    result = await db.execute(stmt)
    return result.mappings().all()

async def apply_rules_to_single_transaction(db: AsyncSession, txn: models.Transaction):
    rules_stmt = select(models.TransactionRule)
    rules_res = await db.execute(rules_stmt)
    rules = rules_res.scalars().all()
    for rule in rules:
        is_match = False
        if rule.match_type == "CONTAINS" and rule.pattern.lower() in txn.merchant_name.lower():
            is_match = True
        elif rule.match_type == "EXACT" and rule.pattern.lower() == txn.merchant_name.lower():
            is_match = True
        if is_match:
            print(f"✨ Auto-Rule Applied: {txn.merchant_name} -> {rule.new_merchant_name}")
            txn.merchant_name = rule.new_merchant_name
            txn.category_id = rule.category_id
            break 

async def get_filtered_transactions(
    db: AsyncSession, 
    page: int, 
    limit: int, 
    search: Optional[str] = None, 
    start_date: Optional[date] = None, 
    end_date: Optional[date] = None, 
    payment_type: Optional[str] = None,
    sort_by: str = "txn_date",
    sort_order: str = "desc"
):
    # 1. Build Filter Conditions
    filters = []
    
    if search:
        search_fmt = f"%{search}%"
        filters.append(or_(
            models.Transaction.merchant_name.ilike(search_fmt),
            models.Category.name.ilike(search_fmt),
            models.Transaction.bank_name.ilike(search_fmt)
        ))
    
    if start_date:
        filters.append(models.Transaction.txn_date >= start_date)
    if end_date:
        filters.append(models.Transaction.txn_date <= end_date)
    if payment_type and payment_type.upper() != "ALL":
        filters.append(models.Transaction.payment_type == payment_type.lower())

    # 2. Query for Total Count
    count_stmt = (
        select(func.count())
        .select_from(models.Transaction)
        .join(models.Category, models.Transaction.category_id == models.Category.id)
    )
    for f in filters:
        count_stmt = count_stmt.where(f)
        
    total_count = await db.scalar(count_stmt)

    # 3. Query for Data
    stmt = (
        select(
            models.Transaction.id,
            models.Transaction.amount,
            models.Transaction.txn_date,
            models.Transaction.payment_type,
            models.Transaction.merchant_name,
            models.Transaction.payment_mode,
            models.Transaction.bank_name,
            models.Transaction.upi_transaction_id,
            models.Transaction.category_id,
            models.Category.name.label("category_name"),   
            models.Category.color.label("category_color")  
        )
        .join(models.Category, models.Transaction.category_id == models.Category.id)
    )

    for f in filters:
        stmt = stmt.where(f)

    # 4. Apply Sorting
    sort_column = getattr(models.Transaction, sort_by, models.Transaction.txn_date)
    if sort_order == "asc":
        stmt = stmt.order_by(sort_column.asc())
    else:
        stmt = stmt.order_by(sort_column.desc())

    # 5. Apply Pagination
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit)

    # 6. Execute
    result = await db.execute(stmt)
    rows = result.mappings().all()
    
    # 7. Calculate Pagination Metadata
    # Integer division ceiling logic to get total pages
    total_pages = (total_count + limit - 1) // limit if limit > 0 else 0

    # 8. Return Exact Schema Structure (✅ Fixes Validation Error)
    return {
        "data": [schemas.TransactionOut.model_validate(row) for row in rows], # Renamed 'items' -> 'data'
        "total": total_count,
        "page": page,
        "limit": limit,         # Renamed 'size' -> 'limit'
        "total_pages": total_pages # Added missing field
    }

async def scan_for_duplicates(db: AsyncSession) -> List[schemas.DuplicateGroup]:
    ignore_stmt = select(models.IgnoredDuplicate)
    ignore_res = await db.execute(ignore_stmt)
    ignored_pairs = set()
    for row in ignore_res.scalars():
        ignored_pairs.add(tuple(sorted((row.txn1_id, row.txn2_id))))
    stmt = select(models.Transaction, models.Category).outerjoin(models.Category).order_by(models.Transaction.amount)
    result = await db.execute(stmt)
    rows = result.all()
    all_txns = []
    for txn, cat in rows:
        t_dict = txn.__dict__
        t_dict['category_name'] = cat.name if cat else "Uncategorized"
        t_dict['category_color'] = cat.color if cat else "#cbd5e1"
        all_txns.append(schemas.TransactionOut(**t_dict))
    grouped_by_amount = defaultdict(list)
    for txn in all_txns:
        grouped_by_amount[round(txn.amount, 2)].append(txn)
    potential_duplicates = []
    for amount, group in grouped_by_amount.items():
        if len(group) < 2: continue
        checked_ids = set()
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                t1 = group[i]
                t2 = group[j]
                id_pair = tuple(sorted((t1.id, t2.id)))
                if t1.id in checked_ids and t2.id in checked_ids: continue
                if id_pair in ignored_pairs: continue 
                if t1.upi_transaction_id and t2.upi_transaction_id:
                    if t1.upi_transaction_id != t2.upi_transaction_id: continue 
                    potential_duplicates.append(schemas.DuplicateGroup(group_id=str(uuid.uuid4()), confidence_score=100, transactions=[t1, t2], warning_message="Identical UPI Transaction ID"))
                    checked_ids.add(t1.id); checked_ids.add(t2.id); continue 
                if not t1.txn_date or not t2.txn_date: continue
                if t1.txn_date != t2.txn_date: continue 
                type1 = t1.payment_type.upper() if t1.payment_type else "UNK"
                type2 = t2.payment_type.upper() if t2.payment_type else "UNK"
                if type1 != type2: continue
                similarity = fuzz.partial_ratio(t1.merchant_name.lower(), t2.merchant_name.lower())
                if similarity > 80:
                    potential_duplicates.append(schemas.DuplicateGroup(group_id=str(uuid.uuid4()), confidence_score=int(similarity), transactions=[t1, t2], warning_message=f"Similar Merchant ({similarity}%)"))
                    checked_ids.add(t1.id); checked_ids.add(t2.id)
    return potential_duplicates

async def resolve_duplicate_transaction(db: AsyncSession, data: schemas.ResolveDuplicate):
    if data.keep_id and data.delete_id:
        stmt = select(models.Transaction).where(models.Transaction.id == data.delete_id)
        result = await db.execute(stmt)
        to_delete = result.scalar_one_or_none()
        if to_delete: await db.delete(to_delete)
    elif not data.keep_id and not data.delete_id:
        id_a, id_b = sorted([data.txn1_id, data.txn2_id])
        existing = await db.execute(select(models.IgnoredDuplicate).where(models.IgnoredDuplicate.txn1_id == id_a, models.IgnoredDuplicate.txn2_id == id_b))
        if not existing.scalar():
            new_ignore = models.IgnoredDuplicate(txn1_id=id_a, txn2_id=id_b)
            db.add(new_ignore)
    await db.commit()
    return {"status": "resolved"}

async def update_transaction_logic(db: AsyncSession, txn_id: int, data: schemas.TransactionUpdate):
    query = select(models.Transaction).where(models.Transaction.id == txn_id)
    result = await db.execute(query)
    txn = result.scalar_one_or_none()
    if not txn: return None
    original_merchant_name = txn.merchant_name
    txn.merchant_name = data.merchant_name
    txn.amount = data.amount
    txn.payment_mode = data.payment_mode
    txn.txn_date = data.txn_date
    txn.category_id = data.category_id
    if data.apply_merchant_to_similar or data.apply_category_to_similar:
        update_values = {}
        if data.apply_merchant_to_similar: update_values["merchant_name"] = data.merchant_name
        if data.apply_category_to_similar: update_values["category_id"] = data.category_id
        if update_values:
            bulk_stmt = (update(models.Transaction).where(models.Transaction.merchant_name == original_merchant_name).where(models.Transaction.id != txn_id).values(**update_values))
            await db.execute(bulk_stmt)
    await db.commit()
    await db.refresh(txn)
    return txn

async def get_staging_transactions(db: AsyncSession):
    stmt = select(models.StagingTransaction).order_by(desc(models.StagingTransaction.received_at))
    result = await db.execute(stmt)
    return result.scalars().all()

async def dismiss_staging_item(db: AsyncSession, staging_id: int, background_tasks: BackgroundTasks):
    stmt = select(models.StagingTransaction).where(models.StagingTransaction.id == staging_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item: return {"status": "already_deleted"}
    email_uid = item.email_uid
    await db.delete(item)
    await db.commit()
    if email_uid: background_tasks.add_task(move_email_in_background, email_uid, NON_TXN_FOLDER)
    return {"status": "dismissed"}

async def convert_staging_to_transaction(db: AsyncSession, data: schemas.StagingConvert, background_tasks: BackgroundTasks):
    stmt = select(models.StagingTransaction).where(models.StagingTransaction.id == data.staging_id)
    result = await db.execute(stmt)
    staging_item = result.scalar_one_or_none()
    if not staging_item: return {"error": "Item not found"}
    email_uid = staging_item.email_uid
    txn_date_obj = data.txn_date
    if isinstance(txn_date_obj, str): txn_date_obj = date.fromisoformat(txn_date_obj)
    new_txn = models.Transaction(merchant_name=data.merchant_name, amount=data.amount, txn_date=txn_date_obj, payment_mode=data.payment_mode, payment_type=data.payment_type, category_id=data.category_id, bank_name="HDFC Bank", upi_transaction_id=None)
    await apply_rules_to_single_transaction(db, new_txn)
    db.add(new_txn)
    await db.delete(staging_item)
    await db.commit()
    if email_uid: background_tasks.add_task(move_email_in_background, email_uid, DEST_FOLDER)
    return {"status": "converted", "transaction_id": new_txn.id}