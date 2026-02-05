"""Multi-agent chatbot system.

This module provides a modular multi-agent architecture for the chatbot,
following the principle: "The LLM is the Brain, but the Backend is the Hands"
- LLM handles planning and natural language
- Python agents execute secure local computations

Main entry point:
    process_chat_message(db, message, session_id) -> Dict

Architecture:
    Orchestrator
    ├── ParserAgent (LLM) → TaskDAG
    ├── Compute Agents (Python)
    │   ├── BudgetAgent
    │   ├── TrendsAgent
    │   ├── ForecastAgent
    │   └── AffordabilityAgent
    └── AggregatorAgent (LLM) → Natural language response
"""

from .orchestrator import process_chat_message, get_orchestrator
from .llm import get_rate_limit_status
from .memory import get_session_manager
from .base import get_registry

__all__ = [
    "process_chat_message",
    "get_rate_limit_status",
    "get_orchestrator",
    "get_session_manager",
    "get_registry",
]
