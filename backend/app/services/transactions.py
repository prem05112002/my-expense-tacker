
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, update, delete
from typing import Optional
from datetime import date
from fastapi import BackgroundTasks
from .. import models, schemas
from .etl import move_email_in_background, NON_TXN_FOLDER

COLOR_PALETTE = [
    "#ef4444", "#f97316", "#f59e0b", "#84cc16", "#10b981", "#06b6d4", 
    "#3b82f6", "#6366f1", "#8b5cf6", "#d946ef", "#f43f5e", "#64748b",
    "#a1a1aa", "#b45309", "#15803d", "#1d4ed8", "#7e22ce", "#be123c"
]

async def get_next_available_color(db: AsyncSession) -> str:
    """
    Fetches all currently used colors from the DB and returns the first 
    color from the palette that is NOT used.
    If all are used, it falls back to a deterministic hash or a random one.
    """
    # 1. Get all used colors
    result = await db.execute(select(models.Category.color))
    used_colors = set(result.scalars().all())

    # 2. Find first unused color
    for color in COLOR_PALETTE:
        if color not in used_colors:
            return color
            
    # 3. Fallback: If all used, pick a random one (or use hash based on something else)
    # For now, let's just cycle back to the first one or pick random
    return random.choice(COLOR_PALETTE)

async def get_filtered_transactions(
    db: AsyncSession,
    page: int,
    limit: int,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    payment_type: Optional[str] = None,
    sort_by: str = "txn_date",
    sort_order: str = "desc",
    category_ids: Optional[list[int]] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    merchant_pattern: Optional[str] = None
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

    # New filters: category_ids, amount range, merchant_pattern
    if category_ids:
        filters.append(models.Transaction.category_id.in_(category_ids))
    if amount_min is not None:
        filters.append(models.Transaction.amount >= amount_min)
    if amount_max is not None:
        filters.append(models.Transaction.amount <= amount_max)
    if merchant_pattern:
        filters.append(models.Transaction.merchant_name.ilike(f"%{merchant_pattern}%"))

    # 2. Query for Total Count
    count_stmt = (
        select(func.count())
        .select_from(models.Transaction)
        .join(models.Category, models.Transaction.category_id == models.Category.id)
    )
    for f in filters:
        count_stmt = count_stmt.where(f)

    total_count = await db.scalar(count_stmt)

    # 2b. Query for Debit Sum
    debit_sum_stmt = (
        select(func.coalesce(func.sum(models.Transaction.amount), 0))
        .select_from(models.Transaction)
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.payment_type == "debit")
    )
    for f in filters:
        debit_sum_stmt = debit_sum_stmt.where(f)

    debit_sum = await db.scalar(debit_sum_stmt)

    # 2c. Query for Credit Sum
    credit_sum_stmt = (
        select(func.coalesce(func.sum(models.Transaction.amount), 0))
        .select_from(models.Transaction)
        .join(models.Category, models.Transaction.category_id == models.Category.id)
        .where(models.Transaction.payment_type == "credit")
    )
    for f in filters:
        credit_sum_stmt = credit_sum_stmt.where(f)

    credit_sum = await db.scalar(credit_sum_stmt)

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
    total_pages = (total_count + limit - 1) // limit if limit > 0 else 0

    # 8. Return Exact Schema Structure
    return {
        "data": [schemas.TransactionOut.model_validate(row) for row in rows],
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "debit_sum": float(debit_sum) if debit_sum else 0.0,
        "credit_sum": float(credit_sum) if credit_sum else 0.0
    }

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