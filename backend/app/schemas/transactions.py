from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class TransactionBase(BaseModel):
    txn_date: Optional[date]
    merchant_name: str
    amount: float
    payment_mode: Optional[str]
    payment_type: str = "DEBIT"
    bank_name: Optional[str]
    upi_transaction_id: Optional[str] = None

class PaginatedResponse(BaseModel):
    data: List[TransactionOut]
    total: int
    page: int
    limit: int
    total_pages: int
    debit_sum: float = 0.0
    credit_sum: float = 0.0

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
    upi_transaction_id: Optional[str] = None
    
    class Config:
        from_attributes = True

class TransactionUpdate(BaseModel):
    merchant_name: str
    amount: float
    payment_mode: str
    txn_date: date
    category_id: Optional[int] = None
    apply_merchant_to_similar: bool = False
    apply_category_to_similar: bool = False