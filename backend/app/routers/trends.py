from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..services import trends as trends_service
from ..schemas import trends as trend_schemas

router = APIRouter(prefix="/trends", tags=["Trends"])


@router.get("/overview", response_model=trend_schemas.TrendsOverview)
async def get_trends_overview(db: AsyncSession = Depends(get_db)):
    """
    Get comprehensive spending trends analysis including:
    - Monthly spending totals
    - Category trends (increasing/decreasing/stable)
    - Seasonal patterns
    - Day-of-week analysis
    - Recurring merchant patterns
    """
    return await trends_service.get_trends_overview(db)


@router.get("/category/{name}", response_model=trend_schemas.CategoryTrendDetail)
async def get_category_trend(name: str, db: AsyncSession = Depends(get_db)):
    """
    Get detailed trend analysis for a specific category.
    """
    return await trends_service.get_category_trend_detail(db, name)


@router.post("/simulate-affordability", response_model=trend_schemas.AffordabilityResult)
async def simulate_affordability(
    simulation: trend_schemas.AffordabilitySimulation,
    db: AsyncSession = Depends(get_db)
):
    """
    Simulate the budget impact of adding a new recurring expense.

    Example: {"monthly_expense": 5000}

    Returns whether you can afford it and the impact on your budget.
    """
    return await trends_service.simulate_affordability(db, simulation)
