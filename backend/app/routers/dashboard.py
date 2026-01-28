from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .. import schemas, services
from ..database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# The Main Dashboard Endpoint (Smart Stats)
@router.get("/", response_model=schemas.FinancialHealthStats)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    return await services.get_financial_health(db)

# Get Settings (for the Settings Modal)
@router.get("/settings", response_model=schemas.UserSettingsUpdate)
async def get_settings(db: AsyncSession = Depends(get_db)):
    settings = await services.get_or_create_settings(db)
    return settings

# Update Settings
@router.put("/settings", response_model=schemas.UserSettingsUpdate)
async def update_settings(data: schemas.UserSettingsUpdate, db: AsyncSession = Depends(get_db)):
    updated = await services.update_settings(db, data)
    return updated