"""Forecast agent for predictive financial operations."""

import time
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ....schemas.agents.task import Task, TaskResult, TaskType
from ....schemas.agents.trace import ExecutionTrace, TraceEventType
from ... import chatbot_compute
from ..base import BaseAgent
from ..chatbot import _get_historical_averages


class ForecastAgent(BaseAgent):
    """Agent handling predictive and projection operations.

    Handles:
    - time_range_spend: Spending for a specific time period
    - average_spending: Average monthly spending by category
    - future_projection: Project future spending/savings
    - custom_scenario: Hypothetical scenario calculations
    - goal_planning: Plan to reach a savings goal
    """

    @property
    def name(self) -> str:
        return "forecast_agent"

    @property
    def handles_task_types(self) -> List[TaskType]:
        return [
            TaskType.TIME_RANGE_SPEND,
            TaskType.AVERAGE_SPENDING,
            TaskType.FUTURE_PROJECTION,
            TaskType.CUSTOM_SCENARIO,
            TaskType.GOAL_PLANNING,
        ]

    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Execute a forecast-related task."""
        start_time = time.time()

        trace.add_event(
            TraceEventType.TASK_STARTED,
            agent=self.name,
            task_id=task.id,
        )

        try:
            if task.type == TaskType.TIME_RANGE_SPEND:
                result = await self._handle_time_range_spend(db, task.params, context)
            elif task.type == TaskType.AVERAGE_SPENDING:
                result = await self._handle_average_spending(db, task.params, context)
            elif task.type == TaskType.FUTURE_PROJECTION:
                result = await self._handle_future_projection(db, task.params, context)
            elif task.type == TaskType.CUSTOM_SCENARIO:
                result = await self._handle_custom_scenario(db, task.params, context)
            elif task.type == TaskType.GOAL_PLANNING:
                result = await self._handle_goal_planning(db, task.params, context)
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

    async def _handle_time_range_spend(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> TaskResult:
        """Calculate spending for a specific time range."""
        result_data = await chatbot_compute.calculate_time_range_spend(
            db,
            category_name=params.get("category_name"),
            months_back=params.get("months_back"),
            relative=params.get("relative"),
            start_date=params.get("start_date"),
            end_date=params.get("end_date"),
            payment_type=params.get("payment_type"),
        )

        # Store for chained operations
        context["time_range_spend"] = result_data

        return TaskResult(
            task_id="",
            task_type=TaskType.TIME_RANGE_SPEND,
            success=True,
            data=result_data,
        )

    async def _handle_average_spending(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> TaskResult:
        """Get average monthly spending."""
        result_data = await chatbot_compute.get_avg_spending_by_category(
            db,
            category_name=params.get("category_name"),
            months_back=params.get("months_back", 3),
        )

        # Store for chained operations
        context["avg_spending"] = result_data

        return TaskResult(
            task_id="",
            task_type=TaskType.AVERAGE_SPENDING,
            success=True,
            data=result_data,
        )

    async def _handle_future_projection(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> TaskResult:
        """Project future spending/savings."""
        months_forward = params.get("months_forward", 6)
        adjustments_raw = params.get("adjustments", [])

        # Convert list of adjustments to dict
        adjustments = {}
        if adjustments_raw:
            for adj in adjustments_raw:
                if isinstance(adj, dict):
                    adjustments[adj.get("category", "")] = adj.get("change_amount", 0)

        result_data = await chatbot_compute.project_future_spending(
            db,
            months_forward=months_forward,
            adjustments=adjustments if adjustments else None,
        )

        # Store for chained operations (e.g., affordability check)
        context["scenario_savings"] = result_data["total_projected_savings"]
        context["monthly_surplus"] = result_data["new_monthly_surplus"]

        return TaskResult(
            task_id="",
            task_type=TaskType.FUTURE_PROJECTION,
            success=True,
            data=result_data,
        )

    async def _handle_custom_scenario(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> TaskResult:
        """Execute a custom hypothetical scenario calculation.

        This calculates projected savings based on spending adjustments.
        """
        adjustments = params.get("adjustments", {})
        months = params.get("months", 6)

        # Get historical averages for projections
        historical = await _get_historical_averages(db, months_back=3)

        avg_budget = historical["avg_monthly_budget"]
        avg_spend = historical["avg_monthly_spend"]
        avg_category_spend = historical["avg_category_spend"]
        current_monthly_surplus = historical["avg_monthly_surplus"]

        # Calculate additional savings from adjustments
        additional_monthly_savings = 0.0
        adjustment_details = {}

        for cat_name, change in adjustments.items():
            # Find matching category (fuzzy match)
            matched_cat = None
            matched_current_spend = 0

            for existing_cat, spend in avg_category_spend.items():
                if cat_name.lower() in existing_cat.lower() or existing_cat.lower() in cat_name.lower():
                    matched_cat = existing_cat
                    matched_current_spend = spend
                    break

            if matched_cat:
                # change is negative for reductions (e.g., -10000)
                reduction = abs(change) if change < 0 else 0
                actual_savings = min(reduction, matched_current_spend)
                additional_monthly_savings += actual_savings
                adjustment_details[matched_cat] = {
                    "current_avg_spend": matched_current_spend,
                    "reduction": actual_savings,
                    "new_avg_spend": matched_current_spend - actual_savings
                }
            else:
                # Category not found, still count the intended reduction
                reduction = abs(change) if change < 0 else 0
                additional_monthly_savings += reduction
                adjustment_details[cat_name] = {
                    "current_avg_spend": 0,
                    "reduction": reduction,
                    "new_avg_spend": 0,
                    "note": "Category not found in historical data"
                }

        # Calculate new monthly surplus with adjustments
        new_monthly_surplus = current_monthly_surplus + additional_monthly_savings

        # Project total savings over the period
        total_projected_savings = new_monthly_surplus * months

        result_data = {
            "adjustments_applied": adjustments,
            "adjustment_details": adjustment_details,
            "avg_monthly_budget": avg_budget,
            "avg_monthly_spend": avg_spend,
            "current_monthly_surplus": current_monthly_surplus,
            "additional_monthly_savings": additional_monthly_savings,
            "new_monthly_surplus": new_monthly_surplus,
            "months_projected": months,
            "total_projected_savings": total_projected_savings,
            "months_of_historical_data": historical["months_of_data"],
        }

        # Store in context for chained operations (affordability check)
        context["scenario_savings"] = total_projected_savings
        context["monthly_surplus"] = new_monthly_surplus
        context["historical"] = historical

        return TaskResult(
            task_id="",
            task_type=TaskType.CUSTOM_SCENARIO,
            success=True,
            data=result_data,
        )

    async def _handle_goal_planning(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> TaskResult:
        """Create a plan to reach a savings goal."""
        result_data = await chatbot_compute.calculate_goal_plan(
            db,
            target_amount=params.get("target_amount", 0),
            target_months=params.get("target_months"),
            goal_name=params.get("goal_name"),
        )

        # Store for chained operations
        context["goal_plan"] = result_data

        return TaskResult(
            task_id="",
            task_type=TaskType.GOAL_PLANNING,
            success=True,
            data=result_data,
        )
