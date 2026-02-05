"""Aggregator agent for formatting results into natural language responses."""

import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ...schemas.agents.task import Task, TaskDAG, TaskResult, TaskType
from ...schemas.agents.trace import ExecutionTrace, TraceEventType
from .base import BaseAgent
from .llm import call_gemini_api, is_valid_llm_response


class AggregatorAgent(BaseAgent):
    """Agent that formats task results into natural language responses.

    Takes the results from compute agents and uses LLM to create
    a conversational response for the user.
    """

    @property
    def name(self) -> str:
        return "aggregator_agent"

    @property
    def handles_task_types(self) -> List[TaskType]:
        return [TaskType.FORMAT_RESPONSE]

    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Not used - aggregator formats responses, doesn't execute tasks."""
        return self._make_result(task, False, error="Aggregator agent formats responses, use format_response method")

    async def format_response(
        self,
        user_query: str,
        dag: TaskDAG,
        results: List[TaskResult],
        trace: ExecutionTrace,
    ) -> str:
        """Format task results into a natural language response.

        Args:
            user_query: Original user query
            dag: The task DAG that was executed
            results: Results from all executed tasks
            trace: Execution trace for logging

        Returns:
            Natural language response string
        """
        start_time = time.time()

        trace.add_event(
            TraceEventType.TASK_STARTED,
            agent=self.name,
            data={"num_results": len(results)},
        )

        # Build structured context from results
        results_summary = []
        key_facts = []

        for r in results:
            if r.success:
                results_summary.append(f"- {r.task_type}: {r.data}")
                key_facts.extend(self._extract_key_facts(r))
            else:
                results_summary.append(f"- {r.task_type}: Failed - {r.error}")

        key_facts_str = "\n".join(f"  • {f}" for f in key_facts) if key_facts else "None"

        prompt = f"""User asked: "{user_query}"

Query analysis: {dag.query_summary}

KEY FACTS (use these numbers in your response):
{key_facts_str}

Full computed results:
{chr(10).join(results_summary)}

Write a natural, conversational response (3-5 sentences) that directly answers the user's question.
IMPORTANT:
- Lead with the answer (yes/no for affordability questions)
- Include specific numbers with ₹ symbol
- Explain the calculation briefly (e.g., "By reducing food by ₹10k/month, you'll save ₹X over Y months")
- If affordable, confirm it confidently. If not, suggest alternatives.
- Write in flowing prose, not bullet points"""

        llm_start = time.time()
        response = await call_gemini_api(
            prompt,
            system_instruction="You are a friendly financial assistant. Give clear, confident, conversational responses with specific numbers.",
            temperature=0.5,  # Allow some creativity for natural responses
        )
        llm_duration = (time.time() - llm_start) * 1000

        trace.add_event(
            TraceEventType.LLM_CALL,
            agent=self.name,
            data={"purpose": "format_response"},
            duration_ms=llm_duration,
        )

        duration_ms = (time.time() - start_time) * 1000

        if not is_valid_llm_response(response):
            # Fallback to structured response
            response = self._build_fallback_response(results)
            trace.add_event(
                TraceEventType.FALLBACK_TRIGGERED,
                agent=self.name,
                data={"reason": "invalid_llm_response"},
                duration_ms=duration_ms,
            )
        else:
            trace.add_event(
                TraceEventType.TASK_COMPLETED,
                agent=self.name,
                data={"response_length": len(response)},
                duration_ms=duration_ms,
            )

        return response

    def _extract_key_facts(self, result: TaskResult) -> List[str]:
        """Extract key facts from a task result for the LLM prompt."""
        facts = []
        d = result.data

        if result.task_type == TaskType.BUDGET_STATUS:
            facts.append(f"Budget: ₹{d.get('budget', 0):,.0f}, Spent: ₹{d.get('spent', 0):,.0f}, Remaining: ₹{d.get('remaining', 0):,.0f}")
            facts.append(f"Status: {d.get('status', 'Unknown')}")

        elif result.task_type == TaskType.CATEGORY_SPEND:
            cat = d.get('category', 'Unknown')
            amt = d.get('amount', 0)
            facts.append(f"Spending on {cat}: ₹{amt:,.0f}")

        elif result.task_type == TaskType.CUSTOM_SCENARIO:
            facts.append(f"With the spending adjustments, monthly surplus increases by ₹{d.get('additional_monthly_savings', 0):,.0f}")
            facts.append(f"Over {d.get('months_projected', 0)} months, total projected savings: ₹{d.get('total_projected_savings', 0):,.0f}")

        elif result.task_type == TaskType.AFFORDABILITY_CHECK:
            product = d.get('product', 'the item')
            price = d.get('product_price', 0)
            can_afford = d.get('can_afford', False)
            facts.append(f"{product} costs approximately ₹{price:,.0f}")
            facts.append(f"Affordable: {'Yes' if can_afford else 'No'}")
            if d.get('recommendation'):
                facts.append(f"Recommendation: {d.get('recommendation')}")

        elif result.task_type == TaskType.TIME_RANGE_SPEND:
            total = d.get('total', 0)
            cat = d.get('matched_category') or d.get('category_filter') or 'all categories'
            period = d.get('period', {})
            facts.append(f"Total spent on {cat}: ₹{total:,.0f}")
            facts.append(f"Period: {period.get('start', '')} to {period.get('end', '')}")

        elif result.task_type == TaskType.AVERAGE_SPENDING:
            if d.get('requested_category'):
                cat_data = d['requested_category']
                facts.append(f"Average monthly spending on {cat_data['name']}: ₹{cat_data['avg_monthly']:,.0f}")
            facts.append(f"Overall average monthly: ₹{d.get('avg_monthly_total', 0):,.0f}")

        elif result.task_type == TaskType.SPENDING_VELOCITY:
            facts.append(f"Spending change: {d.get('change_percent', 0):+.1f}% ({d.get('status', 'unknown')})")
            facts.append(f"Current week: ₹{d.get('current_window', {}).get('spending', 0):,.0f}")

        elif result.task_type == TaskType.FUTURE_PROJECTION:
            facts.append(f"Projected savings over {d.get('months_projected', 0)} months: ₹{d.get('total_projected_savings', 0):,.0f}")
            facts.append(f"New monthly surplus: ₹{d.get('new_monthly_surplus', 0):,.0f}")

        elif result.task_type == TaskType.GOAL_PLANNING:
            facts.append(f"Target amount: ₹{d.get('target_amount', 0):,.0f}")
            if d.get('is_feasible'):
                if d.get('months_needed'):
                    facts.append(f"Achievable in {d.get('months_needed')} months at current rate")
                else:
                    facts.append(f"Required monthly savings: ₹{d.get('required_monthly_savings', 0):,.0f}")
            else:
                facts.append(f"Shortfall per month: ₹{d.get('shortfall_per_month', 0):,.0f}")

        elif result.task_type == TaskType.BUDGET_FORECAST:
            facts.append(f"Forecast: {d.get('message', '')}")
            facts.append(f"Projected remaining: ₹{d.get('projected_remaining', 0):,.0f}")

        elif result.task_type == TaskType.TRENDS_OVERVIEW:
            if d.get('increasing_categories'):
                facts.append(f"Increasing categories: {', '.join(d['increasing_categories'])}")
            if d.get('decreasing_categories'):
                facts.append(f"Decreasing categories: {', '.join(d['decreasing_categories'])}")

        elif result.task_type == TaskType.SAVINGS_ADVICE:
            if d.get('top_expense'):
                top = d['top_expense']
                facts.append(f"Top expense: {top['name']} (₹{top['value']:,.0f})")
            facts.append(f"Burn status: {d.get('burn_status', 'Unknown')}")

        return facts

    def _build_fallback_response(self, results: List[TaskResult]) -> str:
        """Build a structured fallback response when LLM formatting fails."""
        parts = []

        for r in results:
            if not r.success or not r.data:
                continue

            d = r.data

            if r.task_type == TaskType.BUDGET_STATUS:
                parts.append(
                    f"Budget: ₹{d.get('budget', 0):,.0f}, "
                    f"Spent: ₹{d.get('spent', 0):,.0f}, "
                    f"Remaining: ₹{d.get('remaining', 0):,.0f}"
                )

            elif r.task_type == TaskType.CATEGORY_SPEND:
                cat = d.get('category', 'Unknown')
                amt = d.get('amount', 0)
                if d.get('not_found'):
                    parts.append(f"No spending found for '{cat}'.")
                else:
                    parts.append(f"Spending on {cat}: ₹{amt:,.0f}")

            elif r.task_type == TaskType.CUSTOM_SCENARIO:
                parts.append(
                    f"By adjusting your spending, you'll save an additional "
                    f"₹{d.get('additional_monthly_savings', 0):,.0f}/month. "
                    f"Over {d.get('months_projected', 0)} months, that's "
                    f"₹{d.get('total_projected_savings', 0):,.0f} in total savings."
                )

            elif r.task_type == TaskType.AFFORDABILITY_CHECK:
                answer = "Yes" if d.get('can_afford') else "No"
                product = d.get('product', 'item')
                price = d.get('product_price', 0)
                rec = d.get('recommendation', '')
                parts.append(
                    f"{answer}, you can{'not' if not d.get('can_afford') else ''} "
                    f"afford {product} (₹{price:,.0f}). {rec}"
                )

            elif r.task_type == TaskType.TIME_RANGE_SPEND:
                cat = d.get('matched_category') or d.get('category_filter') or 'total'
                parts.append(
                    f"You spent ₹{d.get('total', 0):,.0f} on {cat} "
                    f"({d.get('transaction_count', 0)} transactions)."
                )

            elif r.task_type == TaskType.AVERAGE_SPENDING:
                if d.get('requested_category') and d['requested_category'].get('found'):
                    cat_data = d['requested_category']
                    parts.append(
                        f"Your average monthly spending on {cat_data['name']} is "
                        f"₹{cat_data['avg_monthly']:,.0f}."
                    )
                else:
                    parts.append(
                        f"Average monthly spending: ₹{d.get('avg_monthly_total', 0):,.0f}."
                    )

            elif r.task_type == TaskType.SPENDING_VELOCITY:
                status = d.get('status', 'stable')
                change = d.get('change_percent', 0)
                parts.append(f"Your spending is {status} ({change:+.1f}% vs last week).")

            elif r.task_type == TaskType.FUTURE_PROJECTION:
                parts.append(
                    f"Projected savings over {d.get('months_projected', 0)} months: "
                    f"₹{d.get('total_projected_savings', 0):,.0f} "
                    f"(₹{d.get('new_monthly_surplus', 0):,.0f}/month)."
                )

            elif r.task_type == TaskType.GOAL_PLANNING:
                goal = d.get('goal_name') or f"₹{d.get('target_amount', 0):,.0f}"
                if d.get('is_feasible'):
                    if d.get('months_needed'):
                        parts.append(
                            f"You can reach {goal} in {d.get('months_needed')} months "
                            f"at your current savings rate."
                        )
                    else:
                        parts.append(
                            f"To reach {goal} in {d.get('target_months')} months, "
                            f"save ₹{d.get('required_monthly_savings', 0):,.0f}/month."
                        )
                else:
                    parts.append(
                        f"Reaching {goal} requires cutting "
                        f"₹{d.get('shortfall_per_month', 0):,.0f}/month more."
                    )

            elif r.task_type == TaskType.BUDGET_FORECAST:
                parts.append(d.get('message', 'Budget forecast unavailable.'))

            elif r.task_type == TaskType.CLARIFY:
                parts.append(d.get("question", "Could you provide more details?"))

        if not parts:
            return "I analyzed your query but couldn't generate a response. Please try rephrasing."

        return " ".join(parts)
