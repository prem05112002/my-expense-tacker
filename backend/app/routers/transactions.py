from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
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
    category_ids: Optional[str] = Query(None, description="Comma-separated category IDs"),
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    merchant_pattern: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    # Parse comma-separated category IDs
    parsed_category_ids = None
    if category_ids:
        try:
            parsed_category_ids = [int(cid.strip()) for cid in category_ids.split(",") if cid.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid category_ids format")

    return await services.get_filtered_transactions(
        db, page, limit, search, start_date, end_date, payment_type, sort_by, sort_order,
        category_ids=parsed_category_ids,
        amount_min=amount_min,
        amount_max=amount_max,
        merchant_pattern=merchant_pattern
    )

@router.post("/smart-search", response_model=schemas.SmartSearchResponse)
async def smart_search_transactions(
    request: schemas.SmartSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Smart search endpoint that parses natural language queries into structured filters.
    Examples: "food expenses over 500 last week", "swiggy transactions this month"
    """
    return await services.process_smart_search(db, request)


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

@router.get("/duplicates", response_model=List[schemas.DuplicateGroup])
async def get_potential_duplicates(db: AsyncSession = Depends(get_db)):
    """
    Analyzes transactions to find potential double-entries.
    """
    return await services.scan_for_duplicates(db)

@router.post("/duplicates/resolve")
async def resolve_duplicate(
    data: schemas.ResolveDuplicate,
    db: AsyncSession = Depends(get_db)
):
    await services.resolve_duplicate_pair(db, data)
    return {"message": "Duplicate resolved"}