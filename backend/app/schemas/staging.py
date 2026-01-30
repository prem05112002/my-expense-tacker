from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime

class StagingConvert(BaseModel):
    staging_id: int
    merchant_name: str
    amount: float
    txn_date: date
    payment_mode: Optional[str] = "UPI"
    payment_type: str = "DEBIT"
    category_id: Optional[int] = None

class StagingTransactionOut(BaseModel):
    id: int
    email_subject: str
    received_at: Optional[datetime] 
    email_body: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)