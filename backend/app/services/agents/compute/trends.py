"""Trends agent for spending analysis operations."""

import time
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ....schemas.agents.task import Task, TaskResult, TaskType
from ....schemas.agents.trace import ExecutionTrace, TraceEventType
from ...analytics import calculate_financial_health
from ...trends import get_trends_overview
from ... import chatbot_compute
from ..base import BaseAgent


class TrendsAgent(BaseAgent):
    """Agent handling spending trend and analysis operations.

    Handles:
    - trends_overview: Overall spending trends analysis
    - savings_advice: Suggestions for where to cut spending
    - spending_velocity: Rate of spending change
    """

    @property
    def name(self) -> str:
        return "trends_agent"

    @property
    def handles_task_types(self) -> List[TaskType]:
        return [
            TaskType.TRENDS_OVERVIEW,
            TaskType.SAVINGS_ADVICE,
            TaskType.SPENDING_VELOCITY,
        ]

    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Execute a trends-related task."""
        start_time = time.time()

        trace.add_event(
            TraceEventType.TASK_STARTED,
            agent=self.name,
            task_id=task.id,
        )

        try:
            if task.type == TaskType.TRENDS_OVERVIEW:
                result = await self._handle_trends_overview(db, context)
            elif task.type == TaskType.SAVINGS_ADVICE:
                result = await self._handle_savings_advice(db, context)
            elif task.type == TaskType.SPENDING_VELOCITY:
                result = await self._handle_spending_velocity(db, task.params, context)
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

    async def _handle_trends_overview(
        self,
        db: AsyncSession,
        context: Dict[str, Any],
    ) -> TaskResult:
        """Get spending trends analysis."""
        trends = await get_trends_overview(db)

        # Extract key insights
        increasing = [c.category for c in trends.category_trends if c.trend == "increasing"][:3]
        decreasing = [c.category for c in trends.category_trends if c.trend == "decreasing"][:3]
        high_spend_months = [p.month_name for p in trends.seasonal_patterns if p.is_high_spend]

        data = {
            "increasing_categories": increasing,
            "decreasing_categories": decreasing,
            "high_spend_months": high_spend_months,
            "top_recurring": trends.recurring_patterns[0].merchant_name if trends.recurring_patterns else None,
            "category_trends": [
                {
                    "category": c.category,
                    "trend": c.trend,
                    "change_percent": c.change_percent,
                }
                for c in trends.category_trends[:5]
            ],
        }

        # Store for other agents
        context["trends"] = trends

        return TaskResult(
            task_id="",
            task_type=TaskType.TRENDS_OVERVIEW,
            success=True,
            data=data,
        )

    async def _handle_savings_advice(
        self,
        db: AsyncSession,
        context: Dict[str, Any],
    ) -> TaskResult:
        """Get savings suggestions."""
        # Get health data if not in context
        health = context.get("health")
        if not health:
            health = await calculate_financial_health(db, offset=0)
            context["health"] = health

        # Get trends data if not in context
        trends = context.get("trends")
        if not trends:
            trends = await get_trends_overview(db)
            context["trends"] = trends

        # Find increasing categories (potential savings opportunities)
        increasing = [
            (c.category, c.change_percent)
            for c in trends.category_trends
            if c.trend == "increasing"
        ][:3]

        categories = health.get("category_breakdown", [])

        data = {
            "increasing_categories": increasing,
            "top_expense": categories[0] if categories else None,
            "burn_status": health["burn_rate_status"],
            "remaining_budget": health["budget_remaining"],
            "total_spend": health["total_spend"],
        }

        return TaskResult(
            task_id="",
            task_type=TaskType.SAVINGS_ADVICE,
            success=True,
            data=data,
        )

    async def _handle_spending_velocity(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> TaskResult:
        """Get rate of spending change."""
        window_days = params.get("window_days", 7)

        result_data = await chatbot_compute.get_spending_velocity(
            db,
            window_days=window_days,
        )

        # Store for other agents
        context["velocity"] = result_data

        return TaskResult(
            task_id="",
            task_type=TaskType.SPENDING_VELOCITY,
            success=True,
            data=result_data,
        )
