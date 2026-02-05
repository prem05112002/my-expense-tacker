"""Base agent protocol and registry."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from sqlalchemy.ext.asyncio import AsyncSession

from ...schemas.agents.task import Task, TaskResult, TaskType
from ...schemas.agents.trace import ExecutionTrace


@runtime_checkable
class Agent(Protocol):
    """Protocol defining the interface for all agents."""

    @property
    def name(self) -> str:
        """Agent's unique name."""
        ...

    @property
    def handles_task_types(self) -> List[TaskType]:
        """List of task types this agent can handle."""
        ...

    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Execute a task and return the result.

        Args:
            task: The task to execute
            context: Shared context from previous tasks (results keyed by task_id)
            db: Database session for queries
            trace: Execution trace for logging

        Returns:
            TaskResult with success status and data
        """
        ...


class BaseAgent(ABC):
    """Base class for agents with common functionality."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent's unique name."""
        pass

    @property
    @abstractmethod
    def handles_task_types(self) -> List[TaskType]:
        """List of task types this agent can handle."""
        pass

    @abstractmethod
    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
        db: AsyncSession,
        trace: ExecutionTrace,
    ) -> TaskResult:
        """Execute a task."""
        pass

    def _make_result(
        self,
        task: Task,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_ms: float = 0,
    ) -> TaskResult:
        """Helper to create a TaskResult."""
        return TaskResult(
            task_id=task.id,
            task_type=task.type,
            success=success,
            data=data or {},
            error=error,
            duration_ms=duration_ms,
        )


class AgentRegistry:
    """Registry mapping task types to agents."""

    def __init__(self):
        self._agents: Dict[str, Agent] = {}
        self._task_type_map: Dict[TaskType, str] = {}

    def register(self, agent: Agent) -> None:
        """Register an agent.

        Args:
            agent: Agent instance to register
        """
        self._agents[agent.name] = agent
        for task_type in agent.handles_task_types:
            self._task_type_map[task_type] = agent.name

    def get_agent_for_task(self, task_type: TaskType) -> Optional[Agent]:
        """Get the agent that handles a specific task type.

        Args:
            task_type: The task type to find an agent for

        Returns:
            Agent instance or None if no agent handles this type
        """
        agent_name = self._task_type_map.get(task_type)
        if agent_name:
            return self._agents.get(agent_name)
        return None

    def get_agent(self, name: str) -> Optional[Agent]:
        """Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        return list(self._agents.keys())


# Global registry instance
_registry = AgentRegistry()


def get_registry() -> AgentRegistry:
    """Get the global agent registry."""
    return _registry
