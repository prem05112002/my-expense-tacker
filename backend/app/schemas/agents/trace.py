"""Execution trace schemas for debugging and observability."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid

from .task import TaskDAG


class TraceEventType(str, Enum):
    """Types of events recorded during execution."""
    DAG_CREATED = "dag_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    LLM_CALL = "llm_call"
    CONTEXT_UPDATED = "context_updated"
    SESSION_LOADED = "session_loaded"
    FALLBACK_TRIGGERED = "fallback_triggered"


class TraceEvent(BaseModel):
    """A single event in the execution trace."""
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: TraceEventType
    agent: Optional[str] = None
    task_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[float] = None

    class Config:
        use_enum_values = True


class ExecutionTrace(BaseModel):
    """Complete trace of a query execution for debugging.

    Captures all events, timing, and results for observability.
    """
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id: str
    user_query: str
    events: List[TraceEvent] = Field(default_factory=list)
    total_duration_ms: float = 0
    llm_calls: int = 0
    tasks_executed: int = 0
    tasks_failed: int = 0
    dag: Optional[TaskDAG] = None
    final_response: Optional[str] = None
    success: bool = False
    started_at: datetime = Field(default_factory=datetime.now)

    def add_event(
        self,
        event_type: TraceEventType,
        agent: Optional[str] = None,
        task_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Add an event to the trace."""
        self.events.append(TraceEvent(
            event_type=event_type,
            agent=agent,
            task_id=task_id,
            data=data or {},
            duration_ms=duration_ms,
        ))

        if event_type == TraceEventType.LLM_CALL:
            self.llm_calls += 1
        elif event_type == TraceEventType.TASK_COMPLETED:
            self.tasks_executed += 1
        elif event_type == TraceEventType.TASK_FAILED:
            self.tasks_failed += 1

    def finalize(self, response: Optional[str] = None, success: bool = False) -> None:
        """Finalize the trace with final results."""
        self.final_response = response
        self.success = success
        self.total_duration_ms = (datetime.now() - self.started_at).total_seconds() * 1000
