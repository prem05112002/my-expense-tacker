from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date

from ..database import get_db
from .. import schemas, services

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.get("/", response_model=schemas.PaginatedResponse)
async def read_transactions(
    page: int = 1,
    limit: int = 15,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    payment_type: Optional[str] = None,
    sort_by: str = "txn_date",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db)
):
    return await services.get_filtered_transactions(
        db, page, limit, search, start_date, end_date, payment_type, sort_by, sort_order
    )

@router.put("/{txn_id}")
async def update_transaction(
    txn_id: int,
    data: schemas.TransactionUpdate,
    db: AsyncSession = Depends(get_db)
):
    updated_txn = await services.update_transaction_logic(db, txn_id, data)
    if not updated_txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return {"message": "Transaction updated successfully"}