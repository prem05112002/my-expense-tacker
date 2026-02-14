from datetime import date
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class OperationType(str, Enum):
    """Types of operations the chatbot can execute."""
    # Core operations
    BUDGET_STATUS = "budget_status"
    CATEGORY_SPEND = "category_spend"
    TRENDS_OVERVIEW = "trends_overview"
    AFFORDABILITY_CHECK = "affordability_check"
    SAVINGS_ADVICE = "savings_advice"
    CUSTOM_SCENARIO = "custom_scenario"  # Hypothetical calculations
    CLARIFY = "clarify"  # Ask follow-up question

    # New predictive operations
    FUTURE_PROJECTION = "future_projection"  # Project spending/savings forward
    GOAL_PLANNING = "goal_planning"  # Plan to reach a savings goal
    BUDGET_FORECAST = "budget_forecast"  # Will I stay under budget?
    TIME_RANGE_SPEND = "time_range_spend"  # Spending for specific period
    AVERAGE_SPENDING = "average_spending"  # Average monthly category spending
    SPENDING_VELOCITY = "spending_velocity"  # Rate of spending change


class Operation(BaseModel):
    """A single operation to execute."""
    type: OperationType
    params: Dict[str, Any] = {}
    description: str


class QueryPlan(BaseModel):
    """Plan of operations to execute for a user query."""
    operations: List[Operation]
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    query_summary: str


class OperationResult(BaseModel):
    """Result of executing a single operation."""
    operation_type: OperationType
    success: bool
    data: Dict[str, Any] = {}
    error: Optional[str] = None


# ============================================
# Session and Structured Query Schemas
# ============================================

class TimeRange(BaseModel):
    """Flexible time range specification for queries."""
    months_back: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    relative: Optional[str] = None  # "last_week", "this_month", "last_3_months", etc.


class SpendingAdjustment(BaseModel):
    """A spending adjustment for scenario planning."""
    category: str
    change_amount: float  # Negative for reduction, positive for increase


class ChatQueryParams(BaseModel):
    """
    Structured parameters parsed from natural language query.

    The LLM parses user queries into this structure, then local Python
    functions execute the actual computations.
    """
    operation_type: OperationType
    category_name: Optional[str] = None
    time_range: Optional[TimeRange] = None
    months_forward: Optional[int] = None
    target_amount: Optional[float] = None
    target_months: Optional[int] = None
    goal_name: Optional[str] = None
    adjustments: Optional[List[SpendingAdjustment]] = None
    product_name: Optional[str] = None
    monthly_cost: Optional[float] = None
    reference_previous: bool = False  # For follow-up queries like "what about last month?"


class ChatMessage(BaseModel):
    """A single message in the conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float
    parsed_params: Optional[ChatQueryParams] = None  # For assistant messages, store what was computed


class ChatRequest(BaseModel):
    """Request to the chatbot endpoint."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from the chatbot endpoint."""
    response: str
    intent: str
    requires_llm: bool
    rate_limit: Dict[str, Any]
    session_id: str
    parsed_params: Optional[ChatQueryParams] = None  # The parsed params used for this response
    follow_up_question: Optional[str] = None  # Separate follow-up question (e.g., goal suggestion)
    goal_created: bool = False  # True if a spending goal was created during this request


# ============================================
# Query Plan Schema for LLM (JSON Schema)
# ============================================

def get_query_plan_schema_v2() -> Dict[str, Any]:
    """
    Return JSON schema for ChatQueryParams to enforce structured output from Gemini.

    This schema is used with Gemini's structured output mode (responseSchema)
    to guarantee valid JSON matching our expected structure.
    """
    return {
        "type": "object",
        "properties": {
            "operation_type": {
                "type": "string",
                "enum": [
                    "budget_status", "category_spend", "trends_overview",
                    "affordability_check", "savings_advice", "custom_scenario",
                    "clarify", "future_projection", "goal_planning",
                    "budget_forecast", "time_range_spend", "average_spending",
                    "spending_velocity"
                ]
            },
            "category_name": {"type": ["string", "null"]},
            "time_range": {
                "type": ["object", "null"],
                "properties": {
                    "months_back": {"type": ["integer", "null"]},
                    "start_date": {"type": ["string", "null"]},  # ISO format
                    "end_date": {"type": ["string", "null"]},
                    "relative": {"type": ["string", "null"]}
                }
            },
            "months_forward": {"type": ["integer", "null"]},
            "target_amount": {"type": ["number", "null"]},
            "target_months": {"type": ["integer", "null"]},
            "goal_name": {"type": ["string", "null"]},
            "adjustments": {
                "type": ["array", "null"],
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "change_amount": {"type": "number"}
                    },
                    "required": ["category", "change_amount"]
                }
            },
            "product_name": {"type": ["string", "null"]},
            "monthly_cost": {"type": ["number", "null"]},
            "reference_previous": {"type": "boolean"}
        },
        "required": ["operation_type", "reference_previous"]
    }


def get_multi_operation_schema() -> Dict[str, Any]:
    """
    Return JSON schema for multi-step query plans.

    Some queries require multiple operations in sequence (e.g., custom_scenario + affordability_check).
    This schema supports planning multiple operations.
    """
    return {
        "type": "object",
        "properties": {
            "query_summary": {"type": "string"},
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "budget_status", "category_spend", "trends_overview",
                                "affordability_check", "savings_advice", "custom_scenario",
                                "clarify", "future_projection", "goal_planning",
                                "budget_forecast", "time_range_spend", "average_spending",
                                "spending_velocity"
                            ]
                        },
                        "params": {"type": "object"},
                        "description": {"type": "string"}
                    },
                    "required": ["type", "params", "description"]
                }
            },
            "requires_clarification": {"type": "boolean"},
            "clarification_question": {"type": ["string", "null"]}
        },
        "required": ["query_summary", "operations", "requires_clarification"]
    }
