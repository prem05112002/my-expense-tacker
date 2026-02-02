from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date

class RecurringExpenseBase(BaseModel):
    merchant_name: str
    amount: float
    frequency: str
    next_due_date: date
    category_id: Optional[int] = None

class RecurringExpenseOut(RecurringExpenseBase):
    id: int
    is_active: bool
    confidence_score: int
    category_name: Optional[str] = "Uncategorized"
    
    model_config = ConfigDict(from_attributes=True)

class SubscriptionAction(BaseModel):
    id: int
    action: str # "APPROVE", "REJECT", "UPDATE"