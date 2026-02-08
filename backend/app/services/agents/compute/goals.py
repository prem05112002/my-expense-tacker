"""Goals agent for goal-related operations."""

import time
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ....schemas.agents.task import Task, TaskResult, TaskType
from ....schemas.agents.trace import ExecutionTrace, TraceEventType
from ....schemas.goals import GoalCreate
from ....models import Category
from ...goals import create_goal, get_all_goals_with_progress
from ...analytics import calculate_financial_health
from ..base import BaseAgent


class GoalsAgent(BaseAgent):
    """Agent handling goal-related operations.

    Handles:
    - suggest_goal: Suggest setting a goal for a high-spend category
    - create_goal: Create a new spending goal
    """

    @property
    def name(self) -> str:
        return "goals_agent"

    @property
    def handles_task_types(self) -> List[TaskType]:
        return [
            TaskType.SUGGEST_GOAL,
            TaskType.CREATE_GOAL,
        ]

    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Execute a goal-related task."""
        start_time = time.time()

        trace.add_event(
            TraceEventType.TASK_STARTED,
            agent=self.name,
            task_id=task.id,
        )

        try:
            if task.type == TaskType.SUGGEST_GOAL:
                result = await self._handle_suggest_goal(db, task.params, context)
            elif task.type == TaskType.CREATE_GOAL:
                result = await self._handle_create_goal(db, task.params, context)
            else:
                result = self._make_result(
                    task, False, error=f"Unknown task type: {task.type}"
                )

            duration_ms = (time.time() - start_time) * 1000
            result.duration_ms = duration_ms

            event_type = TraceEventType.TASK_COMPLETED if result.success else TraceEventType.TASK_FAILED
            trace.add_event(
                event_type,
                agent=self.name,
                task_id=task.id,
                data={"success": result.success},
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            trace.add_event(
                TraceEventType.TASK_FAILED,
                agent=self.name,
                task_id=task.id,
                data={"error": str(e)},
                duration_ms=duration_ms,
            )
            return self._make_result(task, False, error=str(e), duration_ms=duration_ms)

    async def _handle_suggest_goal(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> TaskResult:
        """Suggest setting a goal for a category that has high spending.

        This is triggered when a category represents >15% of total spending.
        """
        category_name = params.get("category_name", "")

        # Get health data from context or fetch it
        health = context.get("health")
        if not health:
            health = await calculate_financial_health(db, offset=0)
            context["health"] = health

        # Find the category in breakdown
        categories = health.get("category_breakdown", [])
        total_spend = health.get("total_spend", 0)

        matched = None
        for cat in categories:
            if category_name.lower() in cat["name"].lower():
                matched = cat
                break

        if not matched:
            return TaskResult(
                task_id="",
                task_type=TaskType.SUGGEST_GOAL,
                success=True,
                data={
                    "should_suggest": False,
                    "reason": f"Category '{category_name}' not found in spending data",
                },
            )

        percentage = (matched["value"] / total_spend * 100) if total_spend > 0 else 0

        # Suggest goal if category is >15% of spending
        should_suggest = percentage > 15

        # Get existing goals to avoid suggesting for already-tracked categories
        existing_goals = await get_all_goals_with_progress(db)
        already_has_goal = any(
            g.category_name and g.category_name.lower() == matched["name"].lower()
            for g in existing_goals
        )

        if already_has_goal:
            # Find the existing goal
            existing_goal = next(
                (g for g in existing_goals if g.category_name and g.category_name.lower() == matched["name"].lower()),
                None
            )
            return TaskResult(
                task_id="",
                task_type=TaskType.SUGGEST_GOAL,
                success=True,
                data={
                    "should_suggest": False,
                    "already_has_goal": True,
                    "category": matched["name"],
                    "current_spend": matched["value"],
                    "goal_cap": existing_goal.cap_amount if existing_goal else 0,
                    "progress_percent": existing_goal.progress_percent if existing_goal else 0,
                },
            )

        return TaskResult(
            task_id="",
            task_type=TaskType.SUGGEST_GOAL,
            success=True,
            data={
                "should_suggest": should_suggest,
                "category": matched["name"],
                "current_spend": matched["value"],
                "percentage": round(percentage, 1),
                "suggested_cap": round(matched["value"] * 0.9, -2),  # 10% reduction, rounded to nearest 100
                "reason": f"{matched['name']} makes up {percentage:.1f}% of your spending" if should_suggest else "Spending is within normal range",
            },
        )

    async def _handle_create_goal(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> TaskResult:
        """Create a new spending goal for a category.

        Params:
        - category_name: Name of the category
        - cap_amount: The spending cap (optional, will use suggested if not provided)
        - reduction_percent: Alternative to cap_amount, reduce by X% (optional)
        """
        category_name = params.get("category_name", "")
        cap_amount = params.get("cap_amount")
        reduction_percent = params.get("reduction_percent")

        if not category_name:
            return TaskResult(
                task_id="",
                task_type=TaskType.CREATE_GOAL,
                success=False,
                error="Category name is required to create a goal",
            )

        # Find the category
        stmt = select(Category).where(Category.name.ilike(f"%{category_name}%"))
        result = await db.execute(stmt)
        category = result.scalar_one_or_none()

        if not category:
            return TaskResult(
                task_id="",
                task_type=TaskType.CREATE_GOAL,
                success=False,
                error=f"Category '{category_name}' not found",
            )

        # Get current spending to calculate cap if not provided
        health = context.get("health")
        if not health:
            health = await calculate_financial_health(db, offset=0)
            context["health"] = health

        current_spend = 0
        for cat in health.get("category_breakdown", []):
            if cat["name"].lower() == category.name.lower():
                current_spend = cat["value"]
                break

        # Calculate cap amount
        if cap_amount is None:
            if reduction_percent:
                cap_amount = current_spend * (1 - reduction_percent / 100)
            else:
                # Default: 10% reduction from current spending
                cap_amount = current_spend * 0.9

        cap_amount = max(0, round(cap_amount, -2))  # Round to nearest 100, minimum 0

        # Create the goal
        goal_data = GoalCreate(
            category_id=category.id,
            cap_amount=cap_amount,
            created_via="chatbot",
        )

        new_goal = await create_goal(db, goal_data)

        return TaskResult(
            task_id="",
            task_type=TaskType.CREATE_GOAL,
            success=True,
            data={
                "goal_id": new_goal.id,
                "category": category.name,
                "cap_amount": cap_amount,
                "current_spend": current_spend,
                "message": f"Created a spending cap of ₹{cap_amount:,.0f} for {category.name}",
            },
        )
