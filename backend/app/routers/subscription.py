# backend/app/routers/subscriptions.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ..database import get_db
from .. import services
from ..schemas import subscription as sub_schemas

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

@router.post("/scan")
async def scan_subscriptions(db: AsyncSession = Depends(get_db)):
    """Triggers the AI detection algorithm"""
    return await services.detect_potential_subscriptions(db)

@router.get("/active", response_model=List[sub_schemas.RecurringExpenseOut])
async def get_active(db: AsyncSession = Depends(get_db)):
    return await services.get_subscriptions(db, is_active=True)

@router.get("/potential", response_model=List[sub_schemas.RecurringExpenseOut])
async def get_potential(db: AsyncSession = Depends(get_db)):
    return await services.get_subscriptions(db, is_active=False)

@router.post("/resolve")
async def resolve_subscription(data: sub_schemas.SubscriptionAction, db: AsyncSession = Depends(get_db)):
    return await services.handle_subscription_action(db, data)