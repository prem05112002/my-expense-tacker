from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional
from datetime import date, datetime

def parse_db_string_to_list(v: Any) -> List[str]:
    """Force conversion of DB string 'A,B' to List ['A','B']"""
    if isinstance(v, str):
        return [x.strip() for x in v.split(',')] if v.strip() else []
    if isinstance(v, list):
        return v
    return []

# ==========================================
# 1. BASE MODELS (Shared)
# ==========================================
class CategoryBase(BaseModel):
    name: str
    color: str = "#94a3b8"
    is_income: bool = False

class CategoryOut(CategoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CategoryCreate(CategoryBase):
    pass

class TransactionBase(BaseModel):
    txn_date: Optional[date]
    merchant_name: str
    amount: float
    payment_mode: Optional[str]
    payment_type: str = "DEBIT"
    bank_name: Optional[str]
    upi_transaction_id: Optional[str] = None

# ==========================================
# 2. RESPONSE MODELS (Output to Frontend)
# ==========================================
class PaginatedResponse(BaseModel):
    data: List[TransactionOut]
    total: int
    page: int
    limit: int
    total_pages: int

# ✅ DUPLICATE GROUP SCHEMA (Required for Transactions Page)
class DuplicateGroup(BaseModel):
    group_id: str
    confidence_score: int
    transactions: List[TransactionOut]
    warning_message: str


class TransactionOut(BaseModel):
    id: int
    amount: float
    txn_date: date
    payment_type: str
    merchant_name: str
    category_name: str
    category_color: str
    payment_mode: Optional[str] = None
    bank_name: Optional[str] = None
    
    class Config:
        from_attributes = True

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

# ✅ STAGING / NEEDS REVIEW SCHEMAS (Fixed the Error)
class StagingTransactionOut(BaseModel):
    id: int
    email_subject: str
    received_at: Optional[datetime] 
    email_body: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Alias to prevent errors if referenced as 'StagingTransaction' elsewhere
class StagingTransaction(StagingTransactionOut):
    pass

# ==========================================
# 3. REQUEST MODELS (Input from Frontend)
# ==========================================
class TransactionUpdate(BaseModel):
    merchant_name: str
    amount: float
    payment_mode: str
    txn_date: date
    category_id: Optional[int] = None
    apply_merchant_to_similar: bool = False
    apply_category_to_similar: bool = False

class ResolveDuplicate(BaseModel):
    txn1_id: int
    txn2_id: int
    keep_id: Optional[int] = None
    delete_id: Optional[int] = None

class StagingConvert(BaseModel):
    staging_id: int
    merchant_name: str
    amount: float
    txn_date: date
    payment_mode: Optional[str] = "UPI"
    payment_type: str = "DEBIT"
    category_id: Optional[int] = None

# ✅ RULE ENGINE SCHEMAS
class RuleCreate(BaseModel):
    pattern: str
    new_merchant_name: str = Field(..., alias="newMerchantName")
    category_id: int = Field(..., alias="categoryId")
    match_type: str = Field("CONTAINS", alias="matchType")
    excluded_ids: Optional[List[int]] = Field([], alias="excludedIds") # Not in DB, but kept for API compat
    model_config = ConfigDict(populate_by_name=True)

class RuleOut(RuleCreate):
    id: int
    category_name: str
    category_color: str
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class RulePreviewResult(BaseModel):
    transaction_id: int
    current_name: str
    date: date
    amount: float

class UserSettingsUpdate(BaseModel):
    salary_day: int
    budget_type: str 
    budget_value: float
    # These match the frontend "MultiSelect"
    ignored_categories: List[str] = []   
    income_categories: List[str] = []    
    view_cycle_offset: int = 0

class UserSettingsOut(BaseModel):
    id: int
    salary_day: int
    budget_type: str
    budget_value: float
    monthly_budget: float
    view_cycle_offset: int
    
    # ✅ OUTPUTS AS LISTS
    ignored_categories: List[str]
    income_categories: List[str]

    @field_validator('ignored_categories', 'income_categories', mode='before')
    @classmethod
    def convert(cls, v):
        return parse_db_string_to_list(v)

    model_config = ConfigDict(from_attributes=True)