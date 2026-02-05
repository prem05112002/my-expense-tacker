"""Affordability agent for purchase decisions."""

import re
import time
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ....schemas.agents.task import Task, TaskResult, TaskType
from ....schemas.agents.trace import ExecutionTrace, TraceEventType
from ..llm import call_gemini_api, is_valid_llm_response
from ..base import BaseAgent
from ..chatbot import _get_historical_averages


class AffordabilityAgent(BaseAgent):
    """Agent handling affordability check operations.

    Handles:
    - affordability_check: Check if user can afford a product/service

    This agent may use LLM to look up product prices.
    """

    @property
    def name(self) -> str:
        return "affordability_agent"

    @property
    def handles_task_types(self) -> List[TaskType]:
        return [TaskType.AFFORDABILITY_CHECK]

    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Execute an affordability check."""
        start_time = time.time()

        trace.add_event(
            TraceEventType.TASK_STARTED,
            agent=self.name,
            task_id=task.id,
        )

        try:
            result = await self._handle_affordability_check(db, task.params, context, trace)

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

    async def _handle_affordability_check(
        self,
        db: AsyncSession,
        params: Dict[str, Any],
        context: Dict[str, Any],
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Check if user can afford a product/service."""
        product_name = params.get("product_name", "")
        monthly_cost = params.get("monthly_cost", 0)

        # Get scenario context from previous operations (e.g., custom_scenario)
        scenario_savings = context.get("scenario_savings", 0)
        monthly_surplus = context.get("monthly_surplus", 0)
        historical = context.get("historical")

        # If monthly_cost is 0, get price from LLM
        product_price = 0
        is_one_time_purchase = False

        if monthly_cost <= 0 and product_name:
            price_prompt = f"""What is the estimated price in INR for: "{product_name}"

For one-time purchases (flights, electronics, etc.), give the TOTAL price.
For subscriptions/recurring expenses, give the MONTHLY cost.

Return ONLY in this format:
Product: [name]
Price: [number in INR]
Type: [one-time or monthly]"""

            llm_start = time.time()
            price_response = await call_gemini_api(price_prompt)
            llm_duration = (time.time() - llm_start) * 1000

            trace.add_event(
                TraceEventType.LLM_CALL,
                agent=self.name,
                data={"purpose": "price_lookup", "product": product_name},
                duration_ms=llm_duration,
            )

            if price_response and is_valid_llm_response(price_response):
                # Parse the response
                for line in price_response.split("\n"):
                    line_lower = line.lower()
                    if "price" in line_lower and ":" in line:
                        try:
                            price_str = re.sub(r"[₹$,\s]", "", line.split(":", 1)[1])
                            match = re.search(r"[\d.]+", price_str)
                            if match:
                                product_price = float(match.group())
                        except (ValueError, IndexError):
                            pass
                    elif "type" in line_lower and ":" in line:
                        type_str = line.split(":", 1)[1].strip().lower()
                        is_one_time_purchase = "one" in type_str or "total" in type_str
        else:
            product_price = monthly_cost

        if product_price <= 0:
            return TaskResult(
                task_id="",
                task_type=TaskType.AFFORDABILITY_CHECK,
                success=False,
                error=f"Could not determine price for {product_name}. Try specifying the amount.",
            )

        # Determine affordability based on context
        if scenario_savings > 0:
            # We have projected savings from a custom_scenario
            if is_one_time_purchase:
                # Compare total savings against total price
                can_afford = scenario_savings >= product_price
                affordability_details = {
                    "comparison": "projected_savings vs total_price",
                    "projected_savings": scenario_savings,
                    "product_total_price": product_price,
                    "surplus_after_purchase": scenario_savings - product_price,
                }
            else:
                # Compare new monthly surplus against monthly cost
                can_afford = monthly_surplus >= product_price
                affordability_details = {
                    "comparison": "monthly_surplus vs monthly_cost",
                    "monthly_surplus": monthly_surplus,
                    "monthly_cost": product_price,
                }
        else:
            # No scenario - use current financial state
            if not historical:
                historical = await _get_historical_averages(db, months_back=3)

            if is_one_time_purchase:
                # For one-time purchase, check if current surplus * reasonable months covers it
                months_needed = (
                    product_price / historical["avg_monthly_surplus"]
                    if historical["avg_monthly_surplus"] > 0
                    else float("inf")
                )
                can_afford = months_needed <= 12  # Reasonable timeframe
                affordability_details = {
                    "comparison": "current_savings_rate",
                    "avg_monthly_surplus": historical["avg_monthly_surplus"],
                    "months_to_save": round(months_needed, 1) if months_needed != float("inf") else "Never (no surplus)",
                    "product_total_price": product_price,
                }
            else:
                # Monthly expense - compare against surplus
                can_afford = historical["avg_monthly_surplus"] >= product_price
                affordability_details = {
                    "comparison": "monthly_surplus vs monthly_cost",
                    "avg_monthly_surplus": historical["avg_monthly_surplus"],
                    "monthly_cost": product_price,
                }

        # Generate recommendation
        if can_afford:
            if is_one_time_purchase and scenario_savings > 0:
                recommendation = f"Yes! With your adjusted spending, you'll save ₹{scenario_savings:,.0f} which covers the ₹{product_price:,.0f} cost."
            elif is_one_time_purchase:
                months = affordability_details.get("months_to_save", "unknown")
                recommendation = f"At your current savings rate, you can afford this in about {months} months."
            else:
                recommendation = "This fits within your monthly surplus."
        else:
            if is_one_time_purchase and scenario_savings > 0:
                shortfall = product_price - scenario_savings
                recommendation = f"You'll be ₹{shortfall:,.0f} short. Consider extending the savings period or reducing more."
            else:
                recommendation = "This would exceed your current surplus. Consider cutting other expenses first."

        data = {
            "product": product_name,
            "product_price": product_price,
            "is_one_time_purchase": is_one_time_purchase,
            "can_afford": can_afford,
            "recommendation": recommendation,
            "scenario_applied": scenario_savings > 0,
            **affordability_details,
        }

        return TaskResult(
            task_id="",
            task_type=TaskType.AFFORDABILITY_CHECK,
            success=True,
            data=data,
        )
