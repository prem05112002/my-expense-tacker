"""Parser agent for converting natural language queries to task DAGs."""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ...schemas.agents.task import Task, TaskDAG, TaskResult, TaskType
from ...schemas.agents.trace import ExecutionTrace, TraceEventType
from .base import BaseAgent
from .memory import ConversationSession
from .llm import call_gemini_api, is_valid_llm_response, get_query_plan_schema
from .chatbot import _get_categories, _get_financial_context, _get_historical_averages

logger = logging.getLogger(__name__)


class ParserAgent(BaseAgent):
    """Agent that parses user queries into executable task DAGs.

    Uses LLM to understand natural language queries and creates
    a DAG of tasks to execute, with proper dependencies.
    """

    @property
    def name(self) -> str:
        return "parser_agent"

    @property
    def handles_task_types(self) -> List[TaskType]:
        return [TaskType.PARSE_QUERY]

    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Not used - parser creates the DAG, doesn't execute tasks."""
        return self._make_result(task, False, error="Parser agent creates DAGs, use parse_query method")

    async def parse_query(
        self,
        user_query: str,
        session: ConversationSession,
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> Optional[TaskDAG]:
        """Parse a user query into a TaskDAG.

        Args:
            user_query: Natural language query from user
            session: Conversation session for context
            db: Database session
            trace: Execution trace for logging

        Returns:
            TaskDAG with tasks to execute, or None if parsing fails
        """
        start_time = time.time()

        trace.add_event(
            TraceEventType.TASK_STARTED,
            agent=self.name,
            data={"query": user_query[:100]},
        )

        try:
            # Get context for the LLM
            logger.info(f"[ParserAgent] Parsing query: {user_query[:100]}")
            categories = await _get_categories(db)
            context = await _get_financial_context(db)
            historical = await _get_historical_averages(db, months_back=3)

            logger.debug(f"[ParserAgent] Categories: {categories}")
            logger.debug(f"[ParserAgent] Context: {context}")

            # Format category spend for context
            top_cat_spend = sorted(
                historical['avg_category_spend'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            cat_spend_str = ", ".join([f"{cat}: ₹{amt:,.0f}" for cat, amt in top_cat_spend])

            # Include conversation history for follow-up queries
            conversation_context = session.get_history_for_llm()

            prompt = self._build_prompt(
                user_query=user_query,
                categories=categories,
                context=context,
                historical=historical,
                cat_spend_str=cat_spend_str,
                conversation_context=conversation_context,
            )

            llm_start = time.time()
            logger.info("[ParserAgent] Calling Gemini API...")
            response = await call_gemini_api(
                prompt,
                system_instruction="You are a financial query analyzer. Output valid JSON only.",
                response_schema=get_query_plan_schema(),
                temperature=0,  # Deterministic for structured output
            )
            llm_duration = (time.time() - llm_start) * 1000

            logger.info(f"[ParserAgent] LLM response received in {llm_duration:.0f}ms")
            logger.debug(f"[ParserAgent] Raw response: {response[:500] if response else 'None'}")

            trace.add_event(
                TraceEventType.LLM_CALL,
                agent=self.name,
                data={"purpose": "parse_query"},
                duration_ms=llm_duration,
            )

            if not response:
                logger.warning("[ParserAgent] No response from LLM (API key missing or error)")
                trace.add_event(
                    TraceEventType.TASK_FAILED,
                    agent=self.name,
                    data={"error": "No LLM response"},
                    duration_ms=(time.time() - start_time) * 1000,
                )
                return None

            if not is_valid_llm_response(response):
                logger.warning(f"[ParserAgent] Invalid LLM response: {response[:200]}")
                trace.add_event(
                    TraceEventType.TASK_FAILED,
                    agent=self.name,
                    data={"error": f"Invalid LLM response: {response[:100]}"},
                    duration_ms=(time.time() - start_time) * 1000,
                )
                return None

            dag = self._parse_response(response, user_query)
            if not dag:
                logger.warning(f"[ParserAgent] Failed to parse response into DAG: {response[:200]}")

            duration_ms = (time.time() - start_time) * 1000
            trace.add_event(
                TraceEventType.DAG_CREATED,
                agent=self.name,
                data={
                    "num_tasks": len(dag.tasks) if dag else 0,
                    "requires_clarification": dag.requires_clarification if dag else False,
                },
                duration_ms=duration_ms,
            )

            if dag:
                trace.dag = dag
                logger.info(f"[ParserAgent] Created DAG with {len(dag.tasks)} tasks: {[t.type for t in dag.tasks]}")
            else:
                logger.warning("[ParserAgent] DAG creation returned None")

            return dag

        except Exception as e:
            logger.exception(f"[ParserAgent] Exception during parsing: {e}")
            duration_ms = (time.time() - start_time) * 1000
            trace.add_event(
                TraceEventType.TASK_FAILED,
                agent=self.name,
                data={"error": str(e)},
                duration_ms=duration_ms,
            )
            return None

    def _build_prompt(
        self,
        user_query: str,
        categories: List[str],
        context: Dict[str, Any],
        historical: Dict[str, Any],
        cat_spend_str: str,
        conversation_context: str,
    ) -> str:
        """Build the prompt for the LLM."""
        return f"""You are a financial assistant. Parse the user's question into operations to execute.

CONVERSATION HISTORY (for context on follow-up queries):
{conversation_context}

Available operations:
1. budget_status - Get current budget, spending, and remaining amount
2. category_spend (params: category_name) - Get spending for a specific category
3. trends_overview - Get spending trends analysis
4. affordability_check (params: product_name, monthly_cost) - Check if user can afford something
   - The system will automatically look up the price if monthly_cost=0
5. savings_advice - Get savings suggestions
6. custom_scenario (params: adjustments, months) - Project future savings with spending changes
   - adjustments: dict of category name to monthly change (e.g., {{"Food": -10000}} means reduce food by 10k/month)
   - months: number of months to project
7. time_range_spend (params: category_name, months_back, relative) - Spending for a specific period
   - relative can be: "last_week", "this_month", "last_3_months", etc.
8. average_spending (params: category_name, months_back) - Average monthly spending
9. spending_velocity (params: window_days) - Rate of spending change
10. future_projection (params: months_forward, adjustments) - Project future spending/savings
11. goal_planning (params: target_amount, target_months, goal_name) - Plan to reach a savings goal
12. budget_forecast (params: days_forward) - Forecast budget status for end of cycle

User's categories: {', '.join(categories) if categories else 'Unknown'}

HISTORICAL AVERAGES (past 3 months - USE THESE FOR PROJECTIONS):
- Average monthly budget: ₹{historical['avg_monthly_budget']:,.0f}
- Average monthly spend: ₹{historical['avg_monthly_spend']:,.0f}
- Average monthly surplus (budget - spend): ₹{historical['avg_monthly_surplus']:,.0f}
- Average spend by top categories: {cat_spend_str}

Current cycle: Budget ₹{context['budget']:,.0f}, Spent ₹{context['spent']:,.0f}, Days left: {context['days_left']}

HANDLING FOLLOW-UP QUERIES:
- If the user says "what about X?" or "and for X?", check the conversation history
- Use the same operation type but with the new parameter (category, time range, etc.)

HANDLING COMPLEX QUERIES:
- For queries like "If I reduce X, can I afford Y?", create TWO operations:
  1. custom_scenario with the adjustments
  2. affordability_check with the product
- The affordability_check will use context from custom_scenario

IMPORTANT:
- Never set requires_clarification=true if the query can be answered with the available data
- For product prices, set monthly_cost=0 and the system will look up the price
- Match category names to the user's actual categories (e.g., "fuel" should match "Fuel" if it exists)

OUTPUT FORMAT (respond with ONLY this JSON, no other text):
{{
  "query_summary": "Brief summary of what the user is asking",
  "operations": [
    {{
      "type": "operation_type_here",
      "params": {{"param_name": "value"}},
      "description": "What this operation does"
    }}
  ],
  "requires_clarification": false,
  "clarification_question": null
}}

EXAMPLES:

Query: "How much did I spend on fuel in the past 3 months?"
Response:
{{"query_summary": "Fuel spending over 3 months", "operations": [{{"type": "time_range_spend", "params": {{"category_name": "Fuel", "months_back": 3}}, "description": "Calculate fuel spending for past 3 months"}}], "requires_clarification": false, "clarification_question": null}}

Query: "What about last month?"
Response (assuming previous query was about food):
{{"query_summary": "Food spending last month", "operations": [{{"type": "time_range_spend", "params": {{"category_name": "Food", "relative": "last_month"}}, "description": "Food spending for last month"}}], "requires_clarification": false, "clarification_question": null}}

Query: "What's my budget?"
Response:
{{"query_summary": "Check budget status", "operations": [{{"type": "budget_status", "params": {{}}, "description": "Get current budget status"}}], "requires_clarification": false, "clarification_question": null}}

User query: "{user_query}" """

    def _parse_response(self, response: str, user_query: str) -> Optional[TaskDAG]:
        """Parse LLM response into a TaskDAG."""
        try:
            # Clean up response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(
                    lines[1:-1] if lines[-1].startswith("```") else lines[1:]
                )

            logger.debug(f"[ParserAgent] Parsing JSON: {cleaned[:300]}")
            data = json.loads(cleaned)
            logger.debug(f"[ParserAgent] Parsed data: {data}")

            # Create tasks from operations
            tasks = []
            prev_task_id = None

            operations = data.get("operations", [])
            logger.info(f"[ParserAgent] Found {len(operations)} operations")

            for op_data in operations:
                try:
                    op_type_str = op_data.get("type", "clarify")
                    logger.debug(f"[ParserAgent] Processing operation: {op_type_str}")
                    task_type = TaskType(op_type_str)

                    task = Task(
                        type=task_type,
                        params=op_data.get("params", {}),
                        description=op_data.get("description", ""),
                        # Chain operations: each depends on the previous
                        depends_on=[prev_task_id] if prev_task_id else [],
                    )
                    tasks.append(task)
                    prev_task_id = task.id

                except ValueError as e:
                    # Invalid operation type, skip
                    logger.warning(f"[ParserAgent] Invalid operation type '{op_type_str}': {e}")
                    continue

            if not tasks:
                logger.warning("[ParserAgent] No valid tasks created from operations")
                return None

            return TaskDAG(
                query_summary=data.get("query_summary", user_query),
                tasks=tasks,
                requires_clarification=data.get("requires_clarification", False),
                clarification_question=data.get("clarification_question"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"[ParserAgent] JSON decode error: {e}")
            logger.error(f"[ParserAgent] Response was: {response[:500]}")
            return None
        except (KeyError, TypeError) as e:
            logger.error(f"[ParserAgent] Error parsing response: {e}")
            return None
