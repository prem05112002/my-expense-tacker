from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.get("/", response_model=List[schemas.CategoryOut])
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Category).order_by(models.Category.name))
    return result.scalars().all()

@router.post("/", response_model=schemas.CategoryOut)
async def create_category(req: schemas.CategoryCreate, db: AsyncSession = Depends(get_db)):
    # Check duplicate
    existing = await db.execute(select(models.Category).where(models.Category.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Category already exists")
    
    new_cat = models.Category(name=req.name, color=req.color)
    db.add(new_cat)
    await db.commit()
    await db.refresh(new_cat)
    return new_cat