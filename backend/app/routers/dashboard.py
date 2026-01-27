from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from .. import schemas, services

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/", response_model=schemas.DashboardStats)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    return await services.get_dashboard_metrics(db)