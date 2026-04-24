from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db_for_user
from ..auth import get_current_user_id
from .. import services, schemas


async def get_db(user_id: str = Depends(get_current_user_id)):
    async for session in get_db_for_user(user_id):
        yield session

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# ✅ CHANGE: Add 'offset' parameter here so the backend accepts the dropdown value
@router.get("", response_model=schemas.FinancialHealthStats)
async def get_dashboard_stats(
    offset: int = Query(0, description="Cycle offset (0=current, 1=last month)"), 
    db: AsyncSession = Depends(get_db)
):
    # Pass the offset to the service
    return await services.calculate_financial_health(db, offset=offset)

@router.get("/settings", response_model=schemas.UserSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    return await services.get_or_create_settings(db)

@router.put("/settings", response_model=schemas.UserSettingsOut)
async def update_settings(settings: schemas.UserSettingsUpdate, db: AsyncSession = Depends(get_db)):
    return await services.update_settings(db, settings)