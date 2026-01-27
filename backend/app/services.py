from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, desc, asc, or_
from typing import Optional, List
from datetime import date
from math import ceil

from . import models, schemas

# --- TRANSACTION SERVICES ---

async def get_filtered_transactions(
    db: AsyncSession,
    page: int,
    limit: int,
    search: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
    payment_type: Optional[str],
    sort_by: str,
    sort_order: str
) -> schemas.PaginatedResponse:
    
    # 1. Base Query
    query = select(models.Transaction, models.Category).outerjoin(models.Category)

    # 2. Dynamic Filtering
    if search:
        query = query.where(models.Transaction.merchant_name.ilike(f"%{search}%"))
    if start_date:
        query = query.where(models.Transaction.txn_date >= start_date)
    if end_date:
        query = query.where(models.Transaction.txn_date <= end_date)
    if payment_type and payment_type.upper() != "ALL":
        query = query.where(models.Transaction.payment_type.ilike(payment_type))

    # 3. Count Total (Efficiently)
    count_stmt = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_stmt)
    total_records = total_result.scalar() or 0

    # 4. Sorting
    sort_column = getattr(models.Transaction, sort_by, models.Transaction.txn_date)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    # 5. Pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # 6. Execute & Flatten
    result = await db.execute(query)
    rows = result.all()

    data = []
    for txn, cat in rows:
        t_dict = txn.__dict__
        t_dict['category_name'] = cat.name if cat else "Uncategorized"
        t_dict['category_color'] = cat.color if cat else "#cbd5e1"
        data.append(schemas.TransactionOut(**t_dict))

    return schemas.PaginatedResponse(
        data=data,
        total=total_records,
        page=page,
        limit=limit,
        total_pages=ceil(total_records / limit) if limit > 0 else 0
    )

async def update_transaction_logic(
    db: AsyncSession, 
    txn_id: int, 
    data: schemas.TransactionUpdate
):
    # 1. Fetch Transaction
    query = select(models.Transaction).where(models.Transaction.id == txn_id)
    result = await db.execute(query)
    txn = result.scalar_one_or_none()
    
    if not txn:
        return None

    # 2. Store original merchant (for finding "similar" records)
    original_merchant_name = txn.merchant_name

    # 3. Update Current Transaction
    txn.merchant_name = data.merchant_name
    txn.amount = data.amount
    txn.payment_mode = data.payment_mode
    txn.txn_date = data.txn_date
    txn.category_id = data.category_id

    # 4. BULK UPDATE LOGIC (The "Apply to Similar" feature)
    if data.apply_merchant_to_similar or data.apply_category_to_similar:
        update_values = {}
        
        if data.apply_merchant_to_similar:
            update_values["merchant_name"] = data.merchant_name
        
        if data.apply_category_to_similar:
            update_values["category_id"] = data.category_id
            
        if update_values:
            bulk_stmt = (
                update(models.Transaction)
                .where(models.Transaction.merchant_name == original_merchant_name) # Match OLD name
                .where(models.Transaction.id != txn_id) # Exclude self
                .values(**update_values)
            )
            await db.execute(bulk_stmt)

    await db.commit()
    await db.refresh(txn)
    return txn

# --- DASHBOARD SERVICES ---

async def get_dashboard_metrics(db: AsyncSession):
    # Total Spend
    res_total = await db.execute(select(func.sum(models.Transaction.amount)))
    total_spend = res_total.scalar() or 0.0

    # Uncategorized Count
    res_uncat = await db.execute(
        select(func.count(models.Transaction.id))
        .outerjoin(models.Category)
        .where(or_(models.Transaction.category_id == None, models.Category.name == 'Uncategorized'))
    )
    uncat_count = res_uncat.scalar() or 0

    # Recent Transactions
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

    # Category Breakdown
    stmt_breakdown = (
        select(models.Category.name, func.sum(models.Transaction.amount), models.Category.color)
        .join(models.Transaction)
        .group_by(models.Category.name, models.Category.color)
    )
    res_bd = await db.execute(stmt_breakdown)
    breakdown = [{"name": r[0], "value": r[1], "fill": r[2]} for r in res_bd.all()]

    return schemas.DashboardStats(
        total_spend=total_spend,
        uncategorized_count=uncat_count,
        recent_transactions=recent_flat,
        category_breakdown=breakdown
    )