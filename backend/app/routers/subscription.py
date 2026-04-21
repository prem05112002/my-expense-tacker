# backend/app/routers/subscriptions.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ..database import get_db_for_user
from ..auth import get_current_user_id
from .. import services


async def get_db(user_id: str = Depends(get_current_user_id)):
    async for session in get_db_for_user(user_id):
        yield session
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