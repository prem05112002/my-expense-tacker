"""Orchestrator for multi-agent chatbot execution.

The orchestrator coordinates the flow:
1. Parser Agent creates a TaskDAG from user query
2. Compute Agents execute tasks (parallel when possible)
3. Aggregator Agent formats results into natural language
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from ...schemas.agents.task import Task, TaskDAG, TaskResult, TaskStatus, TaskType
from ...schemas.agents.trace import ExecutionTrace, TraceEventType
from .base import AgentRegistry, get_registry
from .memory import ConversationSession, get_session_manager
from .parser import ParserAgent
from .aggregator import AggregatorAgent
from .llm import get_rate_limit_status, check_rate_limit_for_conversation
from .compute import BudgetAgent, TrendsAgent, ForecastAgent, AffordabilityAgent


class Orchestrator:
    """Coordinates multi-agent execution for chat queries.

    Flow:
    1. Get/create session for conversation continuity
    2. Check rate limits
    3. Parse query into TaskDAG (ParserAgent + LLM)
    4. Execute DAG with topological sort (parallel where possible)
    5. Format response (AggregatorAgent + LLM)
    6. Update session with results
    """

    def __init__(self):
        self.session_manager = get_session_manager()
        self.registry = get_registry()
        self.parser = ParserAgent()
        self.aggregator = AggregatorAgent()

        # Register compute agents
        self._register_agents()

    def _register_agents(self) -> None:
        """Register all compute agents with the registry."""
        agents = [
            BudgetAgent(),
            TrendsAgent(),
            ForecastAgent(),
            AffordabilityAgent(),
        ]
        for agent in agents:
            self.registry.register(agent)

    async def process_query(
        self,
        db: AsyncSession,
        user_query: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a user query through the multi-agent system.

        Args:
            db: Database session
            user_query: User's natural language query
            session_id: Optional session ID for conversation continuity

        Returns:
            Response dict with response text, intent, rate limit info, session_id
        """
        # Get or create session
        session = self.session_manager.get_or_create_session(session_id)

        # Create execution trace
        trace = ExecutionTrace(
            session_id=session.session_id,
            user_query=user_query,
        )

        # Add user message to session
        session.add_message("user", user_query)

        trace.add_event(
            TraceEventType.SESSION_LOADED,
            data={"session_id": session.session_id},
        )

        # Check rate limits
        has_quota, quota_error = check_rate_limit_for_conversation()
        if not has_quota:
            trace.finalize(response=quota_error, success=False)
            return self._make_response(
                response=quota_error,
                intent="rate_limited",
                requires_llm=False,
                session=session,
            )

        try:
            # Step 1: Parse query into TaskDAG
            dag = await self.parser.parse_query(
                user_query=user_query,
                session=session,
                db=db,
                trace=trace,
            )

            if not dag:
                # Fallback to legacy handler
                logger.warning(f"[Orchestrator] Parser returned None, falling back to legacy for: {user_query[:50]}")
                trace.add_event(
                    TraceEventType.FALLBACK_TRIGGERED,
                    data={"reason": "parsing_failed"},
                )
                return await self._legacy_fallback(db, user_query, session, trace)

            # Step 2: Check for clarification
            if dag.requires_clarification and dag.clarification_question:
                response_text = dag.clarification_question
                session.add_message("assistant", response_text)
                trace.finalize(response=response_text, success=True)

                return self._make_response(
                    response=response_text,
                    intent="clarify",
                    requires_llm=True,
                    session=session,
                )

            # Step 3: Execute DAG
            context = await self._execute_dag(dag, db, trace)

            # Collect results
            results = [
                TaskResult(
                    task_id=task.id,
                    task_type=task.type,
                    success=task.status == TaskStatus.COMPLETED,
                    data=task.result or {},
                    error=task.error,
                )
                for task in dag.tasks
            ]

            # Store results in session for follow-up queries
            session.last_results = {
                "tasks": [t.model_dump() for t in dag.tasks],
                "results": [r.model_dump() for r in results],
            }

            # Check for clarification tasks
            for task in dag.tasks:
                if task.type == TaskType.CLARIFY and task.status == TaskStatus.COMPLETED:
                    question = task.result.get("question", "Could you provide more details?") if task.result else "Could you provide more details?"
                    session.add_message("assistant", question)
                    trace.finalize(response=question, success=True)

                    return self._make_response(
                        response=question,
                        intent="clarify",
                        requires_llm=True,
                        session=session,
                    )

            # Step 4: Format response
            response_text = await self.aggregator.format_response(
                user_query=user_query,
                dag=dag,
                results=results,
                trace=trace,
            )

            # Update session
            session.add_message("assistant", response_text)
            trace.finalize(response=response_text, success=True)

            return self._make_response(
                response=response_text,
                intent="conversational",
                requires_llm=True,
                session=session,
            )

        except Exception as e:
            logger.exception(f"[Orchestrator] Exception during query processing: {e}")
            trace.finalize(response=str(e), success=False)
            # Fallback on any error
            return await self._legacy_fallback(db, user_query, session, trace)

    async def _execute_dag(
        self,
        dag: TaskDAG,
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> Dict[str, Any]:
        """Execute all tasks in the DAG.

        Uses topological sort to identify parallel execution opportunities.
        Tasks at the same "level" (no dependencies between them) run in parallel.

        Args:
            dag: TaskDAG to execute
            db: Database session
            trace: Execution trace

        Returns:
            Shared context dict with results from all tasks
        """
        context: Dict[str, Any] = {}
        levels = self._topological_sort(dag.tasks)

        for level_tasks in levels:
            if not level_tasks:
                continue

            # Execute all tasks at this level in parallel
            coroutines = [
                self._execute_task(task, context, db, trace)
                for task in level_tasks
            ]

            results = await asyncio.gather(*coroutines, return_exceptions=True)

            # Process results and update context
            for task, result in zip(level_tasks, results):
                if isinstance(result, Exception):
                    task.status = TaskStatus.FAILED
                    task.error = str(result)
                elif isinstance(result, TaskResult):
                    task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
                    task.result = result.data
                    task.error = result.error

                    # Add to shared context
                    if result.success:
                        context[task.id] = result.data
                        # Also store by task type for convenience
                        # task.type is already a string due to use_enum_values=True in Task model
                        context[task.type] = result.data

                        trace.add_event(
                            TraceEventType.CONTEXT_UPDATED,
                            task_id=task.id,
                            data={"keys": list(result.data.keys())},
                        )

        return context

    async def _execute_task(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Execute a single task using the appropriate agent.

        Args:
            task: Task to execute
            context: Shared context from previous tasks
            db: Database session
            trace: Execution trace

        Returns:
            TaskResult from the agent
        """
        task.status = TaskStatus.RUNNING

        # Find the agent for this task type
        agent = self.registry.get_agent_for_task(task.type)
        if not agent:
            return TaskResult(
                task_id=task.id,
                task_type=task.type,
                success=False,
                error=f"No agent found for task type: {task.type}",
            )

        task.assigned_agent = agent.name

        # Execute
        result = await agent.execute(task, context, db, trace)
        result.task_id = task.id

        return result

    def _topological_sort(self, tasks: List[Task]) -> List[List[Task]]:
        """Sort tasks into execution levels based on dependencies.

        Returns tasks grouped by level:
        - Level 0: tasks with no dependencies (can run in parallel)
        - Level 1: tasks depending only on Level 0 tasks (can run in parallel)
        - etc.

        Args:
            tasks: List of tasks to sort

        Returns:
            List of task lists, one per execution level
        """
        if not tasks:
            return []

        # Build dependency graph
        task_map = {t.id: t for t in tasks}
        in_degree = {t.id: len(t.depends_on) for t in tasks}
        dependents = {t.id: [] for t in tasks}

        for task in tasks:
            for dep_id in task.depends_on:
                if dep_id in dependents:
                    dependents[dep_id].append(task.id)

        # Find all levels using BFS
        levels = []
        remaining = set(task_map.keys())

        while remaining:
            # Find tasks with no remaining dependencies
            ready = [
                tid for tid in remaining
                if in_degree[tid] == 0
            ]

            if not ready:
                # Cycle detected or invalid dependencies
                # Just add remaining tasks as a single level
                levels.append([task_map[tid] for tid in remaining])
                break

            levels.append([task_map[tid] for tid in ready])

            # Remove these tasks and update in-degrees
            for tid in ready:
                remaining.discard(tid)
                for dependent_id in dependents[tid]:
                    if dependent_id in remaining:
                        in_degree[dependent_id] -= 1

        return levels

    async def _legacy_fallback(
        self,
        db: AsyncSession,
        user_query: str,
        session: ConversationSession,
        trace: ExecutionTrace,
    ) -> Dict[str, Any]:
        """Fall back to the legacy regex-based chat processing.

        Args:
            db: Database session
            user_query: User's query
            session: Conversation session
            trace: Execution trace

        Returns:
            Response dict
        """
        from ..chatbot import _legacy_process_chat_message

        trace.add_event(
            TraceEventType.FALLBACK_TRIGGERED,
            data={"reason": "using_legacy_handler"},
        )

        result = await _legacy_process_chat_message(db, user_query, session.session_id)

        session.add_message("assistant", result["response"])
        trace.finalize(response=result["response"], success=True)

        return result

    def _make_response(
        self,
        response: str,
        intent: str,
        requires_llm: bool,
        session: ConversationSession,
    ) -> Dict[str, Any]:
        """Create a standard response dict.

        Args:
            response: Response text
            intent: Detected intent
            requires_llm: Whether LLM was used
            session: Conversation session

        Returns:
            Response dict matching ChatResponse schema
        """
        return {
            "response": response,
            "intent": intent,
            "requires_llm": requires_llm,
            "rate_limit": get_rate_limit_status(),
            "session_id": session.session_id,
        }


# Global orchestrator instance
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


async def process_chat_message(
    db: AsyncSession,
    message: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Main entry point for chat messages.

    This is the function that should be called from the router.

    Args:
        db: Database session
        message: User's message
        session_id: Optional session ID for multi-turn conversations

    Returns:
        Response dict with response text, intent, rate limit info, and session_id
    """
    orchestrator = get_orchestrator()
    return await orchestrator.process_query(db, message, session_id)
