from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from ..database import get_db
from .. import models, schemas, services

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

@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    # Check if rule exists
    result = await db.execute(select(models.TransactionRule).where(models.TransactionRule.id == rule_id))
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    
    return {"message": "Rule deleted successfully"}