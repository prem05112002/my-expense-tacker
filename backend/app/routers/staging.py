from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from .. import schemas, services
from ..database import get_db

router = APIRouter(prefix="/staging", tags=["staging"])

@router.get("/", response_model=List[schemas.StagingTransactionOut])
async def get_items(db: AsyncSession = Depends(get_db)):
    return await services.get_staging_transactions(db)

@router.delete("/{staging_id}")
async def dismiss(staging_id: int, db: AsyncSession = Depends(get_db)):
    return await services.dismiss_staging_item(db, staging_id)

@router.post("/convert")
async def convert(data: schemas.StagingConvert, db: AsyncSession = Depends(get_db)):
    return await services.convert_staging_to_transaction(db, data)