import uuid
from collections import defaultdict
from rapidfuzz import fuzz
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update, delete
from typing import List
from .. import models, schemas  # Go up one level to 'app'

async def scan_for_duplicates(db: AsyncSession) -> List[schemas.DuplicateGroup]:
    # 1. Fetch Ignored Pairs to skip them
    ignore_stmt = select(models.IgnoredDuplicate)
    ignore_res = await db.execute(ignore_stmt)
    ignored_pairs = set()
    for row in ignore_res.scalars():
        # Store as sorted tuple for consistent lookup
        ignored_pairs.add(tuple(sorted((row.txn1_id, row.txn2_id))))

    # 2. Fetch all transactions with Category info
    stmt = (
        select(models.Transaction, models.Category)
        .outerjoin(models.Category, models.Transaction.category_id == models.Category.id)
        .order_by(models.Transaction.amount)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Convert to Pydantic models for easier processing
    all_txns = []
    for txn, cat in rows:
        t_dict = txn.__dict__
        t_dict['category_name'] = cat.name if cat else "Uncategorized"
        t_dict['category_color'] = cat.color if cat else "#cbd5e1"
        all_txns.append(schemas.TransactionOut(**t_dict))

    # 3. Group by Amount (Exact Match) as first pass
    grouped_by_amount = defaultdict(list)
    for txn in all_txns:
        grouped_by_amount[round(txn.amount, 2)].append(txn)

    potential_duplicates = []
    
    # 4. Fuzzy Match within Amount Groups
    for amount, group in grouped_by_amount.items():
        if len(group) < 2: continue
        
        checked_ids = set()
        
        # O(N^2) comparison within small groups
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                t1 = group[i]
                t2 = group[j]

                # Skip if already paired or ignored
                if t1.id in checked_ids or t2.id in checked_ids: continue
                
                # Check against Ignored Table
                if tuple(sorted((t1.id, t2.id))) in ignored_pairs:
                    continue

                # Rule 1: UPI ID Logic (Strict)
                if t1.upi_transaction_id and t2.upi_transaction_id:
                    if t1.upi_transaction_id == t2.upi_transaction_id:
                        # Exact Match -> 100% Duplicate
                        potential_duplicates.append(schemas.DuplicateGroup(
                            group_id=str(uuid.uuid4()), 
                            confidence_score=100, 
                            transactions=[t1, t2], 
                            warning_message="Identical UPI Transaction ID"
                        ))
                        checked_ids.add(t1.id)
                        checked_ids.add(t2.id)
                        continue 
                    else:
                        # ✅ NEW: If both have UPI IDs but they differ -> Definitely NOT duplicates
                        continue 

                # Rule 2: Similar Details (Merchant + Date + Type)
                if not t1.txn_date or not t2.txn_date: continue
                
                # Date must be exactly same for high confidence 
                if t1.txn_date != t2.txn_date: continue 
                
                type1 = t1.payment_type.upper() if t1.payment_type else "UNK"
                type2 = t2.payment_type.upper() if t2.payment_type else "UNK"
                if type1 != type2: continue

                # Merchant Name Fuzzy Match
                similarity = fuzz.partial_ratio(
                    (t1.merchant_name or "").lower(),
                    (t2.merchant_name or "").lower()
                )
                
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

async def resolve_duplicate_pair(db: AsyncSession, data: schemas.ResolveDuplicate):
    """
    Handles two cases:
    1. KEEP ONE: Delete the 'delete_id'.
    2. KEEP BOTH: Add pair (txn1_id, txn2_id) to IgnoredDuplicate table.
    """
    
    # CASE 1: Delete Duplicate
    if data.delete_id:
        # ✅ FIX: Removed the update query for 'potential_duplicate_of_id' 
        # because that column does not exist in your database model.
        
        # Directly delete the transaction
        stmt = delete(models.Transaction).where(models.Transaction.id == data.delete_id)
        await db.execute(stmt)
        await db.commit()
        return {"status": "resolved", "action": "deleted", "id": data.delete_id}

    # CASE 2: Keep Both (Ignore Pair)
    else:
        # Check if already ignored to avoid unique constraint error
        stmt = select(models.IgnoredDuplicate).where(
            or_(
                (models.IgnoredDuplicate.txn1_id == data.txn1_id) & (models.IgnoredDuplicate.txn2_id == data.txn2_id),
                (models.IgnoredDuplicate.txn1_id == data.txn2_id) & (models.IgnoredDuplicate.txn2_id == data.txn1_id)
            )
        )
        existing = await db.execute(stmt)
        if existing.scalar_one_or_none():
            return {"status": "already_ignored"}

        # Insert into IgnoredDuplicate
        new_ignore = models.IgnoredDuplicate(txn1_id=data.txn1_id, txn2_id=data.txn2_id)
        db.add(new_ignore)
        await db.commit()
        return {"status": "resolved", "action": "ignored_pair"}