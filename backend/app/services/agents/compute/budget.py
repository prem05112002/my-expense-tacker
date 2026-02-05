"""Budget agent for budget-related operations."""

import time
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ....schemas.agents.task import Task, TaskResult, TaskType
from ....schemas.agents.trace import ExecutionTrace, TraceEventType
from ...analytics import calculate_financial_health
from ... import chatbot_compute
from ..base import BaseAgent


class BudgetAgent(BaseAgent):
    """Agent handling budget-related operations.

    Handles:
    - budget_status: Current budget, spending, remaining
    - category_spend: Spending for a specific category
    - budget_forecast: Forecast if user will stay under budget
    """

    @property
    def name(self) -> str:
        return "budget_agent"

    @property
    def handles_task_types(self) -> List[TaskType]:
        return [
            TaskType.BUDGET_STATUS,
            TaskType.CATEGORY_SPEND,
            TaskType.BUDGET_FORECAST,
        ]

    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Execute a budget-related task."""
        start_time = time.time()

        trace.add_event(
            TraceEventType.TASK_STARTED,
            agent=self.name,
            task_id=task.id,
        )

        try:
            if task.type == TaskType.BUDGET_STATUS:
                result = await self._handle_budget_status(db, context)
            elif task.type == TaskType.CATEGORY_SPEND:
                result = await self._handle_category_spend(db, task.params, context)
            elif task.type == TaskType.BUDGET_FORECAST:
                result = await self._handle_budget_forecast(db, task.params)
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

    async def _handle_budget_status(
        self,
        db: AsyncSession,
        context: Dict[str, Any],
    ) -> TaskResult:
        """Get current budget status."""
        health = await calculate_financial_health(db, offset=0)

        data = {
            "budget": health["total_budget"],
            "spent": health["total_spend"],
            "remaining": health["budget_remaining"],
            "days_left": health["days_left"],
            "safe_daily": health["safe_to_spend_daily"],
            "status": health["burn_rate_status"],
            "category_breakdown": health.get("category_breakdown", []),
        }

        # Store in context for other agents
        context["health"] = health

        return TaskResult(
            task_id="",  # Will be set by caller
            task_type=TaskType.BUDGET_STATUS,
            success=True,
            data=data,
        )

    async def _handle_category_spend(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> TaskResult:
        """Get spending for a specific category."""
        # Try to use cached health data
        health = context.get("health")
        if not health:
            health = await calculate_financial_health(db, offset=0)
            context["health"] = health

        category_name = params.get("category_name", "")
        categories = health.get("category_breakdown", [])

        # Find matching category (fuzzy)
        matched = None
        for cat in categories:
            if category_name.lower() in cat["name"].lower():
                matched = cat
                break

        if matched:
            total_spend = health["total_spend"]
            data = {
                "category": matched["name"],
                "amount": matched["value"],
                "percentage": (matched["value"] / total_spend * 100) if total_spend > 0 else 0,
            }
        else:
            data = {
                "category": category_name,
                "amount": 0,
                "not_found": True,
                "available_categories": [c["name"] for c in categories[:5]],
            }

        return TaskResult(
            task_id="",
            task_type=TaskType.CATEGORY_SPEND,
            success=True,
            data=data,
        )

    async def _handle_budget_forecast(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
    ) -> TaskResult:
        """Forecast budget status for end of cycle."""
        days_forward = params.get("days_forward", 0)

        result_data = await chatbot_compute.forecast_budget_status(
            db,
            days_forward=days_forward,
        )

        return TaskResult(
            task_id="",
            task_type=TaskType.BUDGET_FORECAST,
            success=True,
            data=result_data,
        )
