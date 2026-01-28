from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import date, datetime

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
class TransactionOut(TransactionBase):
    id: int
    category_name: str = "Uncategorized"
    category_color: str = "#cbd5e1"
    model_config = ConfigDict(from_attributes=True)

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

# ✅ DASHBOARD: Spending Trend Graph Points
class SpendingTrendItem(BaseModel):
    day: int
    date: str
    actual: Optional[float]
    ideal: float

# ✅ DASHBOARD: Financial Health Stats
class FinancialHealthStats(BaseModel):
    # Context
    cycle_start: date
    cycle_end: date
    days_in_cycle: int
    days_passed: int
    days_left: int
    
    # Money
    total_budget: float
    total_spend: float
    budget_remaining: float
    safe_to_spend_daily: float
    
    # Analysis
    burn_rate_status: str
    projected_spend: float      

    # Trends
    prev_cycle_spend_todate: float = 0.0
    spend_diff_percent: float = 0.0
    spending_trend: List[SpendingTrendItem] = [] 
    
    # Data
    recent_transactions: List[TransactionOut]
    category_breakdown: List[dict]

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

class UserSettingsUpdate(BaseModel):
    salary_day: int
    budget_type: str 
    budget_value: float

# ✅ RULE ENGINE SCHEMAS
class RuleCreate(BaseModel):
    pattern: str
    new_merchant_name: str = Field("", alias="newMerchantName")
    category_id: int = Field("", alias="categoryId")
    match_type: str = Field("CONTAINS", alias="matchType")
    excluded_ids: Optional[List[int]] = Field([], alias="excludedIds")
    model_config = ConfigDict(populate_by_name=True)

class RuleOut(RuleCreate):
    id: int
    category_name: str
    category_color: str
    model_config = ConfigDict(from_attributes=True)

class RulePreviewResult(BaseModel):
    transaction_id: int
    current_name: str
    date: date
    amount: float