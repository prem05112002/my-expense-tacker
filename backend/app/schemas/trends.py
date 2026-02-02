from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date


class MonthlySpend(BaseModel):
    month: str  # "YYYY-MM"
    total: float
    transaction_count: int


class WeeklySpend(BaseModel):
    week_start: date
    week_end: date
    total: float
    transaction_count: int


class CategoryTrend(BaseModel):
    category: str
    color: str
    current_month: float
    previous_month: float
    trend: str  # "increasing", "decreasing", "stable"
    change_percent: float


class SeasonalPattern(BaseModel):
    month: int  # 1-12
    month_name: str
    average_spend: float
    is_high_spend: bool


class DayOfWeekSpend(BaseModel):
    day: int  # 0=Monday, 6=Sunday
    day_name: str
    average_spend: float
    transaction_count: int


class RecurringPattern(BaseModel):
    merchant_name: str
    frequency: str  # "weekly", "monthly", "bi-weekly"
    average_amount: float
    occurrence_count: int
    last_occurrence: date


class TrendsOverview(BaseModel):
    monthly_spending: List[MonthlySpend]
    category_trends: List[CategoryTrend]
    seasonal_patterns: List[SeasonalPattern]
    day_of_week_analysis: List[DayOfWeekSpend]
    recurring_patterns: List[RecurringPattern]
    total_transactions_analyzed: int
    analysis_period_start: date
    analysis_period_end: date


class CategoryTrendDetail(BaseModel):
    category: str
    color: str
    monthly_data: List[MonthlySpend]
    average_monthly: float
    total_spend: float
    trend: str
    peak_month: str
    transaction_count: int


class AffordabilitySimulation(BaseModel):
    monthly_expense: float
    duration_months: Optional[int] = 12


class AffordabilityResult(BaseModel):
    can_afford: bool
    current_budget: float
    current_avg_spend: float
    projected_spend_with_new: float
    budget_remaining_after: float
    impact_percent: float
    recommendation: str
