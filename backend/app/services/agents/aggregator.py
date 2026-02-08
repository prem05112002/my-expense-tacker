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
    ) -> Dict[str, Any]:
        """Format task results into a natural language response.

        Args:
            user_query: Original user query
            dag: The task DAG that was executed
            results: Results from all executed tasks
            trace: Execution trace for logging

        Returns:
            Dict with 'response' (main answer) and optional 'follow_up_question'
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

        # Extract follow-up question from results (will be sent as separate message)
        follow_up_question = self._extract_follow_up_question(results)

        prompt = f"""User asked: "{user_query}"

Query analysis: {dag.query_summary}

KEY FACTS (use these numbers in your response):
{key_facts_str}

Full computed results:
{chr(10).join(results_summary)}

Write a natural, conversational response (2-4 sentences) that directly answers the user's question.
IMPORTANT:
- Lead with the answer (yes/no for affordability questions)
- Include specific numbers with ₹ symbol
- Explain the calculation briefly (e.g., "By reducing food by ₹10k/month, you'll save ₹X over Y months")
- If affordable, confirm it confidently. If not, suggest alternatives.
- Write in flowing prose, not bullet points
- DO NOT include any follow-up questions - just answer the user's question
- If user already has a goal for the category, mention it briefly"""

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

        return {
            "response": response,
            "follow_up_question": follow_up_question,
        }

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
            if d.get('percentage'):
                facts.append(f"This is {d['percentage']:.1f}% of total spending")
            # Goal suggestion
            if d.get('already_has_goal'):
                facts.append(f"User already has a spending cap of ₹{d.get('existing_goal_cap', 0):,.0f} for this category")
            elif d.get('suggest_goal'):
                facts.append(f"IMPORTANT: {cat} is a significant expense - suggest setting a budget cap")

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
                if d.get('percentage_of_total'):
                    facts.append(f"This is {d['percentage_of_total']:.1f}% of total spending")
            facts.append(f"Overall average monthly: ₹{d.get('avg_monthly_total', 0):,.0f}")
            # Goal suggestion
            if d.get('already_has_goal'):
                facts.append(f"User already has a spending cap of ₹{d.get('existing_goal_cap', 0):,.0f} for this category")
            elif d.get('suggest_goal'):
                cat_name = d.get('requested_category', {}).get('name', 'this category')
                facts.append(f"IMPORTANT: {cat_name} is a significant expense - suggest setting a budget cap")

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

        elif result.task_type == TaskType.SUGGEST_GOAL:
            cat = d.get('category', 'Unknown')
            if d.get('already_has_goal'):
                facts.append(f"You already have a goal for {cat}: ₹{d.get('goal_cap', 0):,.0f} cap ({d.get('progress_percent', 0):.0f}% used)")
            elif d.get('should_suggest'):
                facts.append(f"{cat} is {d.get('percentage', 0):.1f}% of your spending (₹{d.get('current_spend', 0):,.0f})")
                facts.append(f"Suggested cap: ₹{d.get('suggested_cap', 0):,.0f}")
            else:
                facts.append(f"{cat} spending is within normal range")

        elif result.task_type == TaskType.CREATE_GOAL:
            facts.append(d.get('message', 'Goal created'))
            facts.append(f"Current spend: ₹{d.get('current_spend', 0):,.0f}, Cap: ₹{d.get('cap_amount', 0):,.0f}")

        return facts

    def _extract_follow_up_question(self, results: List[TaskResult]) -> Optional[str]:
        """Extract a follow-up question from results if goal suggestion is appropriate."""
        for r in results:
            if not r.success:
                continue

            d = r.data

            # Check for goal suggestion in category_spend or average_spending
            if r.task_type in (TaskType.CATEGORY_SPEND, TaskType.AVERAGE_SPENDING):
                if d.get('suggest_goal'):
                    # Get category name
                    if r.task_type == TaskType.CATEGORY_SPEND:
                        cat_name = d.get('category', 'this category')
                    else:
                        cat_name = d.get('requested_category', {}).get('name', 'this category')

                    suggested_cap = d.get('suggested_cap', 0)
                    return (
                        f"Would you like me to help set a spending cap for {cat_name}? "
                        f"I can suggest ₹{suggested_cap:,.0f}/month to help you save."
                    )

            # Check for goal suggestion in suggest_goal task
            if r.task_type == TaskType.SUGGEST_GOAL:
                if d.get('should_suggest') and not d.get('already_has_goal'):
                    cat_name = d.get('category', 'this category')
                    suggested_cap = d.get('suggested_cap', 0)
                    return (
                        f"Would you like me to set a spending cap of ₹{suggested_cap:,.0f}/month for {cat_name}?"
                    )

        return None

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
                    parts.append(f"Spending on {cat}: ₹{amt:,.0f}.")
                    if d.get('percentage'):
                        parts.append(f"This makes up {d.get('percentage', 0):.0f}% of your total spending.")
                    # Note: follow-up question for goal suggestion is sent separately
                    if d.get('already_has_goal'):
                        parts.append(
                            f"You already have a spending cap of ₹{d.get('existing_goal_cap', 0):,.0f} for {cat}, "
                            f"and you've used {d.get('existing_goal_progress', 0):.0f}% so far."
                        )

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
                    cat_name = cat_data['name']
                    parts.append(
                        f"Your average monthly spending on {cat_name} is "
                        f"₹{cat_data['avg_monthly']:,.0f}."
                    )
                    if d.get('percentage_of_total'):
                        parts.append(f"This makes up {d.get('percentage_of_total', 0):.0f}% of your total spending.")
                    # Note: follow-up question for goal suggestion is sent separately
                    if d.get('already_has_goal'):
                        parts.append(
                            f"You already have a spending cap of ₹{d.get('existing_goal_cap', 0):,.0f} for {cat_name}, "
                            f"and you've used {d.get('existing_goal_progress', 0):.0f}% so far this month."
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

            elif r.task_type == TaskType.SUGGEST_GOAL:
                cat = d.get('category', 'Unknown')
                if d.get('already_has_goal'):
                    parts.append(
                        f"You already have a spending cap for {cat} at ₹{d.get('goal_cap', 0):,.0f}. "
                        f"You've used {d.get('progress_percent', 0):.0f}% so far."
                    )
                elif d.get('should_suggest'):
                    parts.append(
                        f"{cat} makes up {d.get('percentage', 0):.1f}% of your spending "
                        f"(₹{d.get('current_spend', 0):,.0f}). Would you like me to help set a spending cap? "
                        f"I suggest ₹{d.get('suggested_cap', 0):,.0f}/month."
                    )
                else:
                    parts.append(f"Your {cat} spending looks reasonable at ₹{d.get('current_spend', 0):,.0f}.")

            elif r.task_type == TaskType.CREATE_GOAL:
                parts.append(
                    f"Done! I've set a spending cap of ₹{d.get('cap_amount', 0):,.0f} for {d.get('category', 'this category')}. "
                    f"You can track your progress on the Dashboard."
                )

        if not parts:
            return "I analyzed your query but couldn't generate a response. Please try rephrasing."

        return " ".join(parts)
