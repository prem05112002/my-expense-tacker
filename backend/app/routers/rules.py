from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from .. import schemas, services
from ..database import get_db

router = APIRouter(prefix="/rules", tags=["rules"])

# ✅ New Preview Endpoint
@router.post("/preview", response_model=List[schemas.RulePreviewResult])
async def preview_rule(
    payload: schemas.RuleCreate, # We use RuleCreate to get pattern/match_type
    db: AsyncSession = Depends(get_db)
):
    results = await services.preview_rule_changes(db, payload.pattern, payload.match_type)
    
    # Map to schema
    return [
        schemas.RulePreviewResult(
            transaction_id=t.id, 
            current_name=t.merchant_name, 
            date=t.txn_date, 
            amount=t.amount
        ) for t in results
    ]

@router.post("/", response_model=schemas.RuleOut)
async def create_rule(rule: schemas.RuleCreate, db: AsyncSession = Depends(get_db)):
    return await services.create_rule(db, rule)

@router.get("/", response_model=List[schemas.RuleOut])
async def get_rules(db: AsyncSession = Depends(get_db)):
    return await services.get_all_rules(db)