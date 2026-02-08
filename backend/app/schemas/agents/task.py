"""Task and DAG schemas for the multi-agent chatbot system."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class TaskStatus(str, Enum):
    """Status of a task in the execution pipeline."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    """Types of tasks the agent system can execute.

    Maps to operations from the original chatbot system plus meta operations.
    """
    # Core financial operations (from OperationType)
    BUDGET_STATUS = "budget_status"
    CATEGORY_SPEND = "category_spend"
    TRENDS_OVERVIEW = "trends_overview"
    AFFORDABILITY_CHECK = "affordability_check"
    SAVINGS_ADVICE = "savings_advice"
    CUSTOM_SCENARIO = "custom_scenario"
    CLARIFY = "clarify"

    # Predictive operations
    FUTURE_PROJECTION = "future_projection"
    GOAL_PLANNING = "goal_planning"
    BUDGET_FORECAST = "budget_forecast"
    TIME_RANGE_SPEND = "time_range_spend"
    AVERAGE_SPENDING = "average_spending"
    SPENDING_VELOCITY = "spending_velocity"

    # Goal operations (Little Goals feature)
    SUGGEST_GOAL = "suggest_goal"
    CREATE_GOAL = "create_goal"

    # Meta operations (orchestration)
    PARSE_QUERY = "parse_query"
    FORMAT_RESPONSE = "format_response"


class Task(BaseModel):
    """A single task in the execution DAG.

    Tasks are the unit of work executed by agents. They can depend on
    other tasks, enabling chained operations like:
    custom_scenario -> affordability_check
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: TaskType
    params: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    depends_on: List[str] = Field(default_factory=list)  # Task IDs
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    assigned_agent: Optional[str] = None

    class Config:
        use_enum_values = True


class TaskDAG(BaseModel):
    """Directed Acyclic Graph of tasks to execute.

    Created by the ParserAgent from user queries.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    query_summary: str
    tasks: List[Task] = Field(default_factory=list)
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute (all dependencies completed)."""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        ready = []
        for task in self.tasks:
            if task.status != TaskStatus.PENDING:
                continue
            if all(dep in completed_ids for dep in task.depends_on):
                ready.append(task)
        return ready

    def is_complete(self) -> bool:
        """Check if all tasks are completed or failed."""
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) for t in self.tasks)


class TaskResult(BaseModel):
    """Result of executing a single task."""
    task_id: str
    task_type: TaskType
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0

    class Config:
        use_enum_values = True
