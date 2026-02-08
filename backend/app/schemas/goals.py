from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class GoalBase(BaseModel):
    category_id: int
    cap_amount: float

class GoalCreate(GoalBase):
    created_via: str = "manual"  # "manual" or "chatbot"

class GoalUpdate(BaseModel):
    cap_amount: Optional[float] = None
    is_active: Optional[bool] = None

class GoalOut(GoalBase):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None
    created_via: str
    category_name: Optional[str] = None
    category_color: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class GoalWithProgress(GoalOut):
    current_spend: float = 0.0
    progress_percent: float = 0.0
    is_over_budget: bool = False
