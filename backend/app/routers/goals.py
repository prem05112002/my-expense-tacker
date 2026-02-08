from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ..database import get_db
from ..schemas.goals import GoalCreate, GoalUpdate, GoalOut, GoalWithProgress
from ..services import goals as goals_service

router = APIRouter(prefix="/goals", tags=["Goals"])


@router.get("/", response_model=List[GoalWithProgress])
async def get_goals(db: AsyncSession = Depends(get_db)):
    """Get all active goals with their current progress."""
    return await goals_service.get_all_goals_with_progress(db)


@router.post("/", response_model=GoalOut)
async def create_goal(goal_data: GoalCreate, db: AsyncSession = Depends(get_db)):
    """Create a new spending goal for a category."""
    goal = await goals_service.create_goal(db, goal_data)

    # Fetch category info for response
    from sqlalchemy import select
    from .. import models
    cat_stmt = select(models.Category).where(models.Category.id == goal.category_id)
    cat_result = await db.execute(cat_stmt)
    category = cat_result.scalar_one_or_none()

    return GoalOut(
        id=goal.id,
        category_id=goal.category_id,
        cap_amount=goal.cap_amount,
        is_active=goal.is_active,
        created_at=goal.created_at,
        created_via=goal.created_via,
        category_name=category.name if category else None,
        category_color=category.color if category else None
    )


@router.put("/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: int,
    goal_data: GoalUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing goal."""
    goal = await goals_service.update_goal(db, goal_id, goal_data)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Fetch category info for response
    from sqlalchemy import select
    from .. import models
    cat_stmt = select(models.Category).where(models.Category.id == goal.category_id)
    cat_result = await db.execute(cat_stmt)
    category = cat_result.scalar_one_or_none()

    return GoalOut(
        id=goal.id,
        category_id=goal.category_id,
        cap_amount=goal.cap_amount,
        is_active=goal.is_active,
        created_at=goal.created_at,
        created_via=goal.created_via,
        category_name=category.name if category else None,
        category_color=category.color if category else None
    )


@router.delete("/{goal_id}")
async def delete_goal(goal_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a goal."""
    success = await goals_service.delete_goal(db, goal_id)
    if not success:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"message": "Goal deleted successfully"}
