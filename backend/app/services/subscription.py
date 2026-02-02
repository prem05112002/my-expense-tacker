# backend/app/services/subscription.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta
import statistics
from .. import models

async def create_subscription_from_transaction(db: AsyncSession, txn_id: int):
    # 1. Fetch the Target Transaction
    txn = await db.get(models.Transaction, txn_id)
    if not txn: return None

    # 2. Look Backwards (Find pattern)
    # We look for: Same Merchant + Same Amount (Approx 5% variance)
    stmt = (
        select(models.Transaction)
        .where(
            models.Transaction.merchant_name.ilike(txn.merchant_name),
            models.Transaction.id != txn_id, # Exclude current one
            models.Transaction.txn_date < txn.txn_date
        )
        .order_by(models.Transaction.txn_date.desc())
        .limit(10) # Look at last 10 occurrences
    )
    history = (await db.execute(stmt)).scalars().all()
    
    # Filter by amount (The "Amazon Trap" check)
    # Only keep txns where amount is within 5% of the current txn
    relevant_history = [
        t for t in history 
        if abs(t.amount - txn.amount) < (txn.amount * 0.05)
    ]

    # 3. Infer Frequency & Next Date
    frequency = "MONTHLY" # Default
    next_date = txn.txn_date + timedelta(days=30) # Default

    if len(relevant_history) >= 1:
        # Calculate days between the current txn and the last one
        last_date = relevant_history[0].txn_date
        days_diff = (txn.txn_date - last_date).days
        
        # Simple Frequency Logic
        if 25 <= days_diff <= 35:
            frequency = "MONTHLY"
            next_date = txn.txn_date + timedelta(days=days_diff)
        elif 350 <= days_diff <= 380:
            frequency = "YEARLY"
            next_date = txn.txn_date + timedelta(days=365)
        elif 6 <= days_diff <= 8:
            frequency = "WEEKLY"
            next_date = txn.txn_date + timedelta(days=7)
        else:
            frequency = "IRREGULAR"
            next_date = txn.txn_date + timedelta(days=30) # Fallback

    # 4. Upsert (Update if exists, else Create)
    # Check if we already have a subscription for this merchant/amount
    existing_stmt = select(models.RecurringExpense).where(
        models.RecurringExpense.merchant_name == txn.merchant_name,
        models.RecurringExpense.amount == txn.amount
    )
    existing_sub = (await db.execute(existing_stmt)).scalar_one_or_none()

    if existing_sub:
        existing_sub.next_due_date = next_date
        existing_sub.frequency = frequency
    else:
        new_sub = models.RecurringExpense(
            merchant_name=txn.merchant_name,
            amount=txn.amount,
            frequency=frequency,
            next_due_date=next_date,
            last_transaction_id=txn.id
        )
        db.add(new_sub)

    await db.commit()
    return {"status": "Subscription Created", "frequency": frequency, "next_due": next_date}