from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from .transactions import TransactionOut
from .goals import GoalWithProgress

class SpendingTrendItem(BaseModel):
    day: int
    date: str
    actual: Optional[float] = None
    previous: Optional[float] = None # ✅ Added for Graph
    ideal: Optional[float] = None

class FinancialHealthStats(BaseModel):
    cycle_start: date
    cycle_end: date
    days_in_cycle: int
    days_passed: int
    days_left: int
    total_budget: float
    total_spend: float
    budget_remaining: float
    safe_to_spend_daily: float
    burn_rate_status: str
    projected_spend: float
    
    # ✅ New Fields for "Point-in-Time" Comparison
    prev_cycle_spend_todate: float 
    spend_diff_percent: float
    
    recent_transactions: List[TransactionOut]
    category_breakdown: List[dict]
    spending_trend: List[SpendingTrendItem]
    view_mode: str

    # Goals and Budget Alert
    goals: List[GoalWithProgress] = []
    show_budget_alert: bool = False
    budget_used_percent: float = 0.0