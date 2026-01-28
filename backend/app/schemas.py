from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date, datetime 

# --- BASE MODELS ---
class CategoryBase(BaseModel):
    name: str
    color: str = "#94a3b8"

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

# --- RESPONSE MODELS ---
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

class DashboardStats(BaseModel):
    total_spend: float
    uncategorized_count: int
    recent_transactions: List[TransactionOut]
    category_breakdown: List[dict]

# --- REQUEST MODELS ---
class TransactionUpdate(BaseModel):
    merchant_name: str
    amount: float
    payment_mode: str
    txn_date: date
    category_id: Optional[int] = None
    
    apply_merchant_to_similar: bool = False
    apply_category_to_similar: bool = False

class DuplicateGroup(BaseModel):
    group_id: str
    confidence_score: int
    transactions: List[TransactionOut]
    warning_message: str

class ResolveDuplicate(BaseModel):
    keep_id: Optional[int] = None 
    delete_id: Optional[int] = None 
    txn1_id: int 
    txn2_id: int

# --- STAGING / NEEDS REVIEW MODELS ---

class StagingTransactionOut(BaseModel):
    id: int
    email_uid: str
    email_subject: str
    received_at: Optional[datetime] 
    email_body: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class StagingConvert(BaseModel):
    staging_id: int
    merchant_name: str
    amount: float
    txn_date: date
    payment_mode: Optional[str] = "UPI"
    payment_type: str = "DEBIT"
    category_id: Optional[int] = None