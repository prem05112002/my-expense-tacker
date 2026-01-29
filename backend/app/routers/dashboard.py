from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import services, schemas

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# ✅ CHANGE: Add 'offset' parameter here so the backend accepts the dropdown value
@router.get("/", response_model=schemas.FinancialHealthStats)
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