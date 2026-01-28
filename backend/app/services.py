from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, desc, asc, or_, delete
from typing import Optional, List
from datetime import date
from math import ceil
from rapidfuzz import fuzz 
from collections import defaultdict
import uuid

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
        query = query.order_by(asc(sort_column))

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    data = []
    for txn, cat in rows:
        t_dict = txn.__dict__
        t_dict['category_name'] = cat.name if cat else "Uncategorized"
        t_dict['category_color'] = cat.color if cat else "#cbd5e1"
        data.append(schemas.TransactionOut(**t_dict))

    return schemas.PaginatedResponse(
        data=data, total=total_records, page=page, limit=limit, 
        total_pages=ceil(total_records / limit) if limit > 0 else 0
    )

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

async def get_dashboard_metrics(db: AsyncSession):
    res_total = await db.execute(select(func.sum(models.Transaction.amount)))
    total_spend = res_total.scalar() or 0.0

    res_uncat = await db.execute(
        select(func.count(models.Transaction.id))
        .outerjoin(models.Category)
        .where(or_(models.Transaction.category_id == None, models.Category.name == 'Uncategorized'))
    )
    uncat_count = res_uncat.scalar() or 0

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

    stmt_breakdown = (
        select(models.Category.name, func.sum(models.Transaction.amount), models.Category.color)
        .join(models.Transaction)
        .group_by(models.Category.name, models.Category.color)
    )
    res_bd = await db.execute(stmt_breakdown)
    breakdown = [{"name": r[0], "value": r[1], "fill": r[2]} for r in res_bd.all()]

    return schemas.DashboardStats(
        total_spend=total_spend, uncategorized_count=uncat_count,
        recent_transactions=recent_flat, category_breakdown=breakdown
    )

# --- DUPLICATE DETECTION SERVICES ---

async def scan_for_duplicates(db: AsyncSession) -> List[schemas.DuplicateGroup]:
    """
    Scans DB for potential duplicates.
    Logic:
    1. If BOTH have UPI IDs: Compare them. Same = Duplicate. Different = Not Duplicate.
    2. If EITHER is missing UPI ID: Compare Amount + Date + Type + Fuzzy Name.
    """
    
    # 1. Fetch Ignored List
    ignore_stmt = select(models.IgnoredDuplicate)
    ignore_res = await db.execute(ignore_stmt)
    ignored_pairs = set()
    for row in ignore_res.scalars():
        ignored_pairs.add((row.txn1_id, row.txn2_id))

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

    # 3. Group by Amount (Rounded to prevent float errors)
    grouped_by_amount = defaultdict(list)
    for txn in all_txns:
        grouped_by_amount[round(txn.amount, 2)].append(txn)

    potential_duplicates = []

    # 4. Analyze each group
    for amount, group in grouped_by_amount.items():
        if len(group) < 2: continue
        
        checked_ids = set()
        
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                t1 = group[i]
                t2 = group[j]

                # Identify IDs for Ignore Check
                id_a, id_b = sorted((t1.id, t2.id))

                if t1.id in checked_ids and t2.id in checked_ids: continue
                if (id_a, id_b) in ignored_pairs: continue 

                # ----------------------------------
                # PRIORITY 1: UPI REFERENCE CHECK
                # ----------------------------------
                # We strictly rely on UPI IDs *only if both* transactions have them.
                if t1.upi_transaction_id and t2.upi_transaction_id:
                    if t1.upi_transaction_id == t2.upi_transaction_id:
                        # 100% Match
                        potential_duplicates.append(schemas.DuplicateGroup(
                            group_id=str(uuid.uuid4()),
                            confidence_score=100,
                            transactions=[t1, t2],
                            warning_message="Identical UPI Transaction ID"
                        ))
                        checked_ids.add(t1.id)
                        checked_ids.add(t2.id)
                        continue # Found match, move to next
                    else:
                        # If UPI IDs exist but differ, they are definitely NOT duplicates.
                        # Skip the fuzzy check.
                        continue

                # ----------------------------------
                # PRIORITY 2: FUZZY LOGIC (Fallback)
                # ----------------------------------
                # This runs if one or both UPI IDs are missing (None or empty).
                
                # A. Strict Date Match
                if not t1.txn_date or not t2.txn_date: continue
                if t1.txn_date != t2.txn_date: continue 

                # B. Strict Payment Type Match (Case Insensitive)
                type1 = t1.payment_type.upper() if t1.payment_type else "UNK"
                type2 = t2.payment_type.upper() if t2.payment_type else "UNK"
                if type1 != type2: continue

                # C. Partial Fuzzy Match
                similarity = fuzz.partial_ratio(t1.merchant_name.lower(), t2.merchant_name.lower())
                
                if similarity > 80:
                    potential_duplicates.append(schemas.DuplicateGroup(
                        group_id=str(uuid.uuid4()),
                        confidence_score=int(similarity),
                        transactions=[t1, t2],
                        warning_message=type1
                    ))
                    
                    checked_ids.add(t1.id)
                    checked_ids.add(t2.id)

    return potential_duplicates

async def resolve_duplicate_pair(db: AsyncSession, data: schemas.ResolveDuplicate):
    if data.delete_id:
        # DELETE Logic
        stmt = delete(models.Transaction).where(models.Transaction.id == data.delete_id)
        await db.execute(stmt)
    else:
        # IGNORE Logic
        id_a, id_b = sorted((data.txn1_id, data.txn2_id))
        
        existing = await db.execute(
            select(models.IgnoredDuplicate)
            .where(models.IgnoredDuplicate.txn1_id == id_a)
            .where(models.IgnoredDuplicate.txn2_id == id_b)
        )
        if not existing.scalar():
            new_ignore = models.IgnoredDuplicate(txn1_id=id_a, txn2_id=id_b)
            db.add(new_ignore)
    
    await db.commit()
    return {"status": "resolved"}

async def get_staging_transactions(db: AsyncSession):
    # Sort by received_at descending
    stmt = select(models.StagingTransaction).order_by(desc(models.StagingTransaction.received_at))
    result = await db.execute(stmt)
    return result.scalars().all()

async def convert_staging_to_transaction(db: AsyncSession, data: schemas.StagingConvert):
    # 1. Fetch Item
    stmt = select(models.StagingTransaction).where(models.StagingTransaction.id == data.staging_id)
    result = await db.execute(stmt)
    staging_item = result.scalar_one_or_none()
    
    if not staging_item:
        return {"error": "Item not found"}

    # 2. Create Transaction
    # (Note: Convert string date to object if needed, depending on your Transaction model)
    txn_date_obj = date.fromisoformat(str(data.txn_date))

    new_txn = models.Transaction(
        merchant_name=data.merchant_name,
        amount=data.amount,
        txn_date=txn_date_obj,
        payment_mode=data.payment_mode,
        payment_type=data.payment_type,
        category_id=data.category_id
    )
    db.add(new_txn)

    # 3. Delete from Unmatched
    await db.delete(staging_item)
    await db.commit()
    
    return {"status": "converted", "new_txn_id": new_txn.id}

async def dismiss_staging_item(db: AsyncSession, staging_id: int):
    """Permanently deletes an item from the unmatched_emails table"""
    # 1. Find the item
    stmt = select(models.StagingTransaction).where(models.StagingTransaction.id == staging_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        # If not found, it might already be deleted. Return success to keep UI happy.
        return {"status": "already_deleted"}

    # 2. Delete it
    await db.delete(item)
    await db.commit()
    return {"status": "deleted"}