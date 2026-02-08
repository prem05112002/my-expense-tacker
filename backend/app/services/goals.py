from datetime import date
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from .. import models
from ..schemas.goals import GoalCreate, GoalUpdate, GoalWithProgress
from .rules import get_or_create_settings


async def get_all_goals(db: AsyncSession) -> List[models.MonthlyGoal]:
    """Fetches all goals with their category info."""
    stmt = (
        select(models.MonthlyGoal)
        .options()
        .order_by(models.MonthlyGoal.id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_active_goals(db: AsyncSession) -> List[models.MonthlyGoal]:
    """Fetches only active goals."""
    stmt = (
        select(models.MonthlyGoal)
        .where(models.MonthlyGoal.is_active == True)
        .order_by(models.MonthlyGoal.id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_goal_by_id(db: AsyncSession, goal_id: int) -> Optional[models.MonthlyGoal]:
    """Fetches a single goal by ID."""
    stmt = select(models.MonthlyGoal).where(models.MonthlyGoal.id == goal_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_goal_by_category(db: AsyncSession, category_id: int) -> Optional[models.MonthlyGoal]:
    """Fetches an active goal for a specific category."""
    stmt = (
        select(models.MonthlyGoal)
        .where(
            models.MonthlyGoal.category_id == category_id,
            models.MonthlyGoal.is_active == True
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_goal(
    db: AsyncSession,
    goal_data: GoalCreate
) -> models.MonthlyGoal:
    """Creates a new monthly goal. Deactivates any existing goal for the same category."""
    # Deactivate existing goal for this category if any
    existing = await get_goal_by_category(db, goal_data.category_id)
    if existing:
        existing.is_active = False

    new_goal = models.MonthlyGoal(
        category_id=goal_data.category_id,
        cap_amount=goal_data.cap_amount,
        created_via=goal_data.created_via
    )
    db.add(new_goal)
    await db.commit()
    await db.refresh(new_goal)
    return new_goal


async def update_goal(
    db: AsyncSession,
    goal_id: int,
    goal_data: GoalUpdate
) -> Optional[models.MonthlyGoal]:
    """Updates an existing goal."""
    goal = await get_goal_by_id(db, goal_id)
    if not goal:
        return None

    if goal_data.cap_amount is not None:
        goal.cap_amount = goal_data.cap_amount
    if goal_data.is_active is not None:
        goal.is_active = goal_data.is_active

    await db.commit()
    await db.refresh(goal)
    return goal


async def delete_goal(db: AsyncSession, goal_id: int) -> bool:
    """Deletes a goal by ID."""
    goal = await get_goal_by_id(db, goal_id)
    if not goal:
        return False

    await db.delete(goal)
    await db.commit()
    return True


async def get_category_spend_for_cycle(
    db: AsyncSession,
    category_id: int,
    start_date: date,
    end_date: date
) -> float:
    """Calculates total spending for a category within a date range."""
    stmt = (
        select(func.coalesce(func.sum(models.Transaction.amount), 0.0))
        .where(
            models.Transaction.category_id == category_id,
            models.Transaction.txn_date >= start_date,
            models.Transaction.txn_date <= end_date,
            func.lower(models.Transaction.payment_type) == 'debit'
        )
    )
    result = await db.execute(stmt)
    return float(result.scalar() or 0.0)


async def get_all_goals_with_progress(db: AsyncSession) -> List[GoalWithProgress]:
    """
    Fetches all active goals with their current spending progress.
    Uses the current billing cycle dates.
    """
    # Import here to avoid circular import
    from .analytics import get_secure_cycle_dates

    settings = await get_or_create_settings(db)
    income_cats = [x.strip() for x in settings.income_categories.split(',')] if settings.income_categories else []

    start_date, end_date = await get_secure_cycle_dates(db, settings.salary_day, 0, income_cats)

    goals = await get_active_goals(db)
    result = []

    for goal in goals:
        # Fetch category info
        cat_stmt = select(models.Category).where(models.Category.id == goal.category_id)
        cat_result = await db.execute(cat_stmt)
        category = cat_result.scalar_one_or_none()

        if not category:
            continue

        # Calculate current spend for this category
        current_spend = await get_category_spend_for_cycle(
            db, goal.category_id, start_date, end_date
        )

        # Calculate progress
        progress_percent = (current_spend / goal.cap_amount * 100) if goal.cap_amount > 0 else 0.0
        is_over_budget = current_spend > goal.cap_amount

        result.append(GoalWithProgress(
            id=goal.id,
            category_id=goal.category_id,
            cap_amount=goal.cap_amount,
            is_active=goal.is_active,
            created_at=goal.created_at,
            created_via=goal.created_via,
            category_name=category.name,
            category_color=category.color,
            current_spend=round(current_spend, 2),
            progress_percent=round(min(progress_percent, 100), 1),
            is_over_budget=is_over_budget
        ))

    return result
