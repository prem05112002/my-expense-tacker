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
# 🔌 CONNECT TO ETL DIRECTORY (Sibling to Backend)
# ==========================================
try:
    current_dir = os.path.dirname(os.path.abspath(__file__)) # /app
    backend_dir = os.path.dirname(current_dir)               # /backend
    project_root = os.path.dirname(backend_dir)              # / (Root)
    
    etl_path = os.path.join(project_root, "Etl") # Adjusted to match your folder casing if needed
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
# ⚙️ SETTINGS & PAYDAY LOGIC (The Missing Part)
# ==========================================
async def get_or_create_settings(db: AsyncSession):
    stmt = select(models.UserSettings)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = models.UserSettings(
            salary_day=1, 
            monthly_budget=50000.0,
            budget_type="FIXED",
            budget_value=50000.0
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        
    return settings

async def update_settings(db: AsyncSession, data: schemas.UserSettingsUpdate):
    settings = await get_or_create_settings(db)
    settings.salary_day = data.salary_day
    settings.budget_type = data.budget_type
    settings.budget_value = data.budget_value
    # Recalculate monthly budget for backward compatibility if needed, 
    # but strictly we rely on budget_value now.
    settings.monthly_budget = data.budget_value 
    
    await db.commit()
    return settings

def get_adjusted_payday(year: int, month: int, base_day: int = 25) -> date:
    # Initialize Country Holidays (India)
    country_holidays = holidays.country_holidays('IN', years=year)
    
    try:
        target_date = date(year, month, base_day)
    except ValueError:
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        target_date = date(year, month, last_day)

    # Walk backwards until we find a working day
    while True:
        is_weekend = target_date.weekday() >= 5 # 5=Sat, 6=Sun
        is_holiday = target_date in country_holidays
        
        if not is_weekend and not is_holiday:
            return target_date
        
        target_date -= timedelta(days=1)

def calculate_cycle_dates(salary_day: int):
    today = date.today()
    current_month_payday = get_adjusted_payday(today.year, today.month, salary_day)
    
    if today >= current_month_payday:
        start_date = current_month_payday
        next_month_year = today.year + 1 if today.month == 12 else today.year
        next_month = 1 if today.month == 12 else today.month + 1
        next_month_payday = get_adjusted_payday(next_month_year, next_month, salary_day)
        end_date = next_month_payday - timedelta(days=1)
    else:
        prev_month_year = today.year - 1 if today.month == 1 else today.year
        prev_month = 12 if today.month == 1 else today.month - 1
        start_date = get_adjusted_payday(prev_month_year, prev_month, salary_day)
        end_date = current_month_payday - timedelta(days=1)
        
    return start_date, end_date

# ==========================================
# 📊 SMART DASHBOARD SERVICES
# ==========================================
async def get_financial_health(db: AsyncSession):
    # 1. Get Settings
    settings = await get_or_create_settings(db)
    
    cycle_start = None
    cycle_end = None
    total_budget = 0.0
    
    # 2. DETERMINE CYCLE & BUDGET
    if settings.budget_type == "PERCENTAGE":
        # Find last Salary
        stmt = (
            select(models.Transaction)
            .join(models.Category)
            .where(models.Category.is_income == True)
            .order_by(desc(models.Transaction.txn_date))
            .limit(1)
        )
        result = await db.execute(stmt)
        last_salary_txn = result.scalar_one_or_none()
        
        if last_salary_txn:
            cycle_start = last_salary_txn.txn_date
            # Logic: End date is day before next expected salary? 
            # Simplified: 30 days projection for dynamic
            try:
                cycle_end = cycle_start.replace(month=cycle_start.month + 1) - timedelta(days=1)
            except ValueError:
                cycle_end = cycle_start.replace(year=cycle_start.year + 1, month=1) - timedelta(days=1)
                
            total_budget = last_salary_txn.amount * (settings.budget_value / 100.0)
        else:
            # Fallback
            cycle_start, cycle_end = calculate_cycle_dates(settings.salary_day)
            total_budget = 50000.0 
    else:
        # FIXED MODE
        cycle_start, cycle_end = calculate_cycle_dates(settings.salary_day)
        total_budget = settings.budget_value

    # Map variables for query
    start_date = cycle_start
    end_date = cycle_end

    # 3. Calculate Math
    today = date.today()
    days_in_cycle = (end_date - start_date).days + 1
    days_passed = (today - start_date).days
    
    if days_passed < 0: days_passed = 0
    if days_passed > days_in_cycle: days_passed = days_in_cycle
        
    days_left = days_in_cycle - days_passed

    # 4. Get Total Spend
    res_total = await db.execute(
        select(func.sum(models.Transaction.amount))
        .where(models.Transaction.txn_date >= start_date, 
               models.Transaction.txn_date <= end_date,
               models.Transaction.payment_type == "DEBIT")
    )
    total_spend = res_total.scalar() or 0.0
    
    budget_remaining = total_budget - total_spend
    safe_daily = budget_remaining / days_left if days_left > 0 else 0.0
    
    # Burn Rate
    ideal_spend_so_far = (total_budget / days_in_cycle) * days_passed
    
    if total_spend > total_budget:
        status = "Critical"
    elif total_spend > ideal_spend_so_far * 1.1:
        status = "Red"
    elif total_spend > ideal_spend_so_far:
        status = "Yellow"
    else:
        status = "Green"

    projected_spend = (total_spend / days_passed) * days_in_cycle if days_passed > 0 else total_spend

    # 5. Recent Transactions
    stmt_recent = (
        select(models.Transaction, models.Category)
        .outerjoin(models.Category)
        .order_by(desc(models.Transaction.txn_date))
        .limit(5)
    )
    res_recent = await db.execute(stmt_recent)
    recent_flat = []
    for txn, cat in res_recent.all():
        t_dict = txn.__dict__
        t_dict['category_name'] = cat.name if cat else "Uncategorized"
        t_dict['category_color'] = cat.color if cat else "#cbd5e1"
        recent_flat.append(schemas.TransactionOut(**t_dict))

    # 6. Category Breakdown
    stmt_breakdown = (
        select(models.Category.name, func.sum(models.Transaction.amount), models.Category.color)
        .join(models.Transaction)
        .where(models.Transaction.txn_date >= start_date, 
               models.Transaction.txn_date <= end_date,
               models.Transaction.payment_type == "DEBIT")
        .group_by(models.Category.name, models.Category.color)
        .order_by(desc(func.sum(models.Transaction.amount)))
        .limit(5)
    )
    res_bd = await db.execute(stmt_breakdown)
    breakdown = [{"name": r[0], "value": r[1], "color": r[2]} for r in res_bd.all()]

    return {
        "cycle_start": start_date,
        "cycle_end": end_date,
        "days_in_cycle": days_in_cycle,
        "days_passed": days_passed,
        "days_left": days_left,
        "total_budget": total_budget,
        "total_spend": total_spend,
        "budget_remaining": budget_remaining,
        "safe_to_spend_daily": safe_daily,
        "burn_rate_status": status,
        "projected_spend": projected_spend,
        "recent_transactions": recent_flat,
        "category_breakdown": breakdown
    }

# ==========================================
# 🧠 RULE ENGINE SERVICES
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
    
    # Fetch Category Details for Response
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
        .values(
            merchant_name=rule.new_merchant_name,
            category_id=rule.category_id
        )
    )

    if excluded_ids:
        stmt = stmt.where(models.Transaction.id.not_in(excluded_ids))

    stmt = stmt.execution_options(synchronize_session=False) 
    
    await db.execute(stmt)
    await db.commit()

async def get_all_rules(db: AsyncSession):
    stmt = select(models.TransactionRule, models.Category).join(models.Category)
    result = await db.execute(stmt)
    rules = []
    for r, c in result:
        r_dict = r.__dict__
        r_dict['category_name'] = c.name
        r_dict['category_color'] = c.color
        rules.append(r_dict)
    return rules

async def apply_rules_to_single_transaction(db: AsyncSession, txn: models.Transaction):
    """
    Checks if a new transaction matches any existing rule.
    If it does, updates the merchant name and category AUTOMATICALLY.
    """
    # 1. Fetch all active rules
    rules_stmt = select(models.TransactionRule)
    rules_res = await db.execute(rules_stmt)
    rules = rules_res.scalars().all()
    
    # 2. Check for matches
    for rule in rules:
        is_match = False
        
        # Case-insensitive comparison
        if rule.match_type == "CONTAINS" and rule.pattern.lower() in txn.merchant_name.lower():
            is_match = True
        elif rule.match_type == "EXACT" and rule.pattern.lower() == txn.merchant_name.lower():
            is_match = True
            
        if is_match:
            print(f"✨ Auto-Rule Applied: {txn.merchant_name} -> {rule.new_merchant_name}")
            txn.merchant_name = rule.new_merchant_name
            txn.category_id = rule.category_id
            break # Stop after first match (Priority to older rules, or you can add priority logic later)

# ==========================================
# 🧾 TRANSACTION & DUPLICATE SERVICES
# ==========================================
async def get_filtered_transactions(
    db: AsyncSession, page: int, limit: int, search: Optional[str],
    start_date: Optional[date], end_date: Optional[date], payment_type: Optional[str],
    sort_by: str, sort_order: str
) -> schemas.PaginatedResponse:
    query = select(models.Transaction, models.Category).outerjoin(models.Category)

    if search:
        query = query.where(models.Transaction.merchant_name.ilike(f"%{search}%"))
    if start_date:
        query = query.where(models.Transaction.txn_date >= start_date)
    if end_date:
        query = query.where(models.Transaction.txn_date <= end_date)
    if payment_type and payment_type.upper() != "ALL":
        query = query.where(models.Transaction.payment_type.ilike(payment_type))

    count_stmt = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_stmt)
    total_records = total_result.scalar() or 0

    sort_column = getattr(models.Transaction, sort_by, models.Transaction.txn_date)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    data = []
    for txn, cat in rows:
        txn_dict = schemas.TransactionOut.model_validate(txn)
        if cat:
            txn_dict.category_name = cat.name
            txn_dict.category_color = cat.color
        data.append(txn_dict)

    return schemas.PaginatedResponse(
        data=data, total=total_records, page=page, limit=limit,
        total_pages=(total_records // limit) + (1 if total_records % limit > 0 else 0)
    )

async def scan_for_duplicates(db: AsyncSession) -> List[schemas.DuplicateGroup]:
    # 1. Fetch Ignored List
    ignore_stmt = select(models.IgnoredDuplicate)
    ignore_res = await db.execute(ignore_stmt)
    ignored_pairs = set()
    for row in ignore_res.scalars():
        ignored_pairs.add(tuple(sorted((row.txn1_id, row.txn2_id))))

    # 2. Fetch all transactions
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
                    if t1.upi_transaction_id != t2.upi_transaction_id:
                        continue 
                    potential_duplicates.append(schemas.DuplicateGroup(
                        group_id=str(uuid.uuid4()),
                        confidence_score=100,
                        transactions=[t1, t2],
                        warning_message="Identical UPI Transaction ID"
                    ))
                    checked_ids.add(t1.id)
                    checked_ids.add(t2.id)
                    continue 

                # Fuzzy Logic
                if not t1.txn_date or not t2.txn_date: continue
                if t1.txn_date != t2.txn_date: continue 
                
                type1 = t1.payment_type.upper() if t1.payment_type else "UNK"
                type2 = t2.payment_type.upper() if t2.payment_type else "UNK"
                if type1 != type2: continue

                similarity = fuzz.partial_ratio(t1.merchant_name.lower(), t2.merchant_name.lower())
                
                if similarity > 80:
                    potential_duplicates.append(schemas.DuplicateGroup(
                        group_id=str(uuid.uuid4()),
                        confidence_score=int(similarity),
                        transactions=[t1, t2],
                        warning_message=f"Similar Merchant ({similarity}%)"
                    ))
                    checked_ids.add(t1.id)
                    checked_ids.add(t2.id)

    return potential_duplicates

async def resolve_duplicate_transaction(db: AsyncSession, data: schemas.ResolveDuplicate):
    if data.keep_id and data.delete_id:
        stmt = select(models.Transaction).where(models.Transaction.id == data.delete_id)
        result = await db.execute(stmt)
        to_delete = result.scalar_one_or_none()
        if to_delete:
            await db.delete(to_delete)
    elif not data.keep_id and not data.delete_id:
        id_a, id_b = sorted([data.txn1_id, data.txn2_id])
        existing = await db.execute(
            select(models.IgnoredDuplicate).where(
                models.IgnoredDuplicate.txn1_id == id_a,
                models.IgnoredDuplicate.txn2_id == id_b
            )
        )
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
            bulk_stmt = (
                update(models.Transaction)
                .where(models.Transaction.merchant_name == original_merchant_name)
                .where(models.Transaction.id != txn_id)
                .values(**update_values)
            )
            await db.execute(bulk_stmt)

    await db.commit()
    await db.refresh(txn)
    return txn

# ==========================================
# 🚀 STAGING / NEEDS REVIEW SERVICES
# ==========================================
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

    if email_uid:
        background_tasks.add_task(move_email_in_background, email_uid, NON_TXN_FOLDER)
    
    return {"status": "dismissed"}

async def convert_staging_to_transaction(db: AsyncSession, data: schemas.StagingConvert, background_tasks: BackgroundTasks):
    stmt = select(models.StagingTransaction).where(models.StagingTransaction.id == data.staging_id)
    result = await db.execute(stmt)
    staging_item = result.scalar_one_or_none()
    
    if not staging_item: return {"error": "Item not found"}

    email_uid = staging_item.email_uid
    txn_date_obj = data.txn_date
    if isinstance(txn_date_obj, str):
        txn_date_obj = date.fromisoformat(txn_date_obj)

    new_txn = models.Transaction(
        merchant_name=data.merchant_name,
        amount=data.amount,
        txn_date=txn_date_obj,
        payment_mode=data.payment_mode,
        payment_type=data.payment_type,
        category_id=data.category_id,
        bank_name="HDFC Bank",
        upi_transaction_id=None
    )
    
    # ✅ Apply Rules
    await apply_rules_to_single_transaction(db, new_txn)

    db.add(new_txn)
    await db.delete(staging_item)
    await db.commit()
    
    if email_uid:
        background_tasks.add_task(move_email_in_background, email_uid, DEST_FOLDER)
    
    return {"status": "converted", "transaction_id": new_txn.id}