"""Tracing utilities for debugging and observability."""

import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from ...schemas.agents.trace import ExecutionTrace, TraceEventType


@contextmanager
def trace_task(
    trace: ExecutionTrace,
    task_id: str,
    agent_name: str,
) -> Generator[Dict[str, Any], None, None]:
    """Context manager for tracing task execution.

    Records start/end events and measures duration.

    Args:
        trace: ExecutionTrace to record events to
        task_id: ID of the task being executed
        agent_name: Name of the agent executing the task

    Yields:
        Dict to populate with result data (for the completion event)
    """
    start_time = time.time()
    result_data: Dict[str, Any] = {}

    trace.add_event(
        TraceEventType.TASK_STARTED,
        agent=agent_name,
        task_id=task_id,
    )

    try:
        yield result_data
        duration_ms = (time.time() - start_time) * 1000
        trace.add_event(
            TraceEventType.TASK_COMPLETED,
            agent=agent_name,
            task_id=task_id,
            data=result_data,
            duration_ms=duration_ms,
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        trace.add_event(
            TraceEventType.TASK_FAILED,
            agent=agent_name,
            task_id=task_id,
            data={"error": str(e)},
            duration_ms=duration_ms,
        )
        raise


def trace_llm_call(
    trace: ExecutionTrace,
    agent_name: str,
    prompt_preview: str,
    response_preview: Optional[str] = None,
    duration_ms: float = 0,
) -> None:
    """Record an LLM call in the trace.

    Args:
        trace: ExecutionTrace to record to
        agent_name: Name of the agent making the call
        prompt_preview: First ~100 chars of the prompt
        response_preview: First ~100 chars of the response
        duration_ms: Call duration in milliseconds
    """
    trace.add_event(
        TraceEventType.LLM_CALL,
        agent=agent_name,
        data={
            "prompt_preview": prompt_preview[:100] + "..." if len(prompt_preview) > 100 else prompt_preview,
            "response_preview": (response_preview[:100] + "..." if response_preview and len(response_preview) > 100 else response_preview),
        },
        duration_ms=duration_ms,
    )


def trace_context_update(
    trace: ExecutionTrace,
    task_id: str,
    context_keys: list,
) -> None:
    """Record a context update in the trace.

    Args:
        trace: ExecutionTrace to record to
        task_id: ID of the task that produced the context
        context_keys: Keys added/updated in the shared context
    """
    trace.add_event(
        TraceEventType.CONTEXT_UPDATED,
        task_id=task_id,
        data={"keys": context_keys},
    )


def format_trace_summary(trace: ExecutionTrace) -> str:
    """Format a trace into a human-readable summary.

    Args:
        trace: ExecutionTrace to summarize

    Returns:
        Formatted summary string
    """
    lines = [
        f"Trace {trace.trace_id} ({trace.user_query[:50]}...)",
        f"  Duration: {trace.total_duration_ms:.0f}ms",
        f"  LLM calls: {trace.llm_calls}",
        f"  Tasks: {trace.tasks_executed} completed, {trace.tasks_failed} failed",
        f"  Success: {trace.success}",
    ]

    if trace.dag:
        lines.append(f"  DAG: {len(trace.dag.tasks)} tasks")
        for task in trace.dag.tasks:
            deps = f" (depends on: {', '.join(task.depends_on)})" if task.depends_on else ""
            lines.append(f"    - {task.id}: {task.type}{deps} [{task.status}]")

    return "\n".join(lines)
