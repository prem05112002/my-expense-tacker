from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# ==========================================
# 1️⃣ AUTHENTICATION & ONBOARDING
# ==========================================

class UserSignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str  # This is the Google App Password
    folder_base_name: str # e.g., "MyExpenses"

class LoginRequest(BaseModel):
    username: str
    password: str

class APIResponse(BaseModel):
    """Generic response for success/fail messages"""
    status: str
    message: str


# ==========================================
# 2️⃣ BANK CONFIGURATION (Registry)
# ==========================================

class CustomBankRequest(BaseModel):
    """For when a user adds a niche bank manually"""
    nickname: str
    email: EmailStr

class BankSelectionRequest(BaseModel):
    """Payload for saving tracked banks"""
    user_id: int
    bank_ids: List[int] # IDs from GlobalBank
    custom_banks: List[CustomBankRequest] = []


# ==========================================
# 3️⃣ TRANSACTIONS & DASHBOARD
# ==========================================

class TransactionUpdate(BaseModel):
    """
    Used when a user manually fixes a transaction in the Resolution Center.
    Everything is optional because they might only fix the Amount.
    """
    amount: Optional[float] = None
    merchant: Optional[str] = None
    category: Optional[str] = None

class TransactionResponse(BaseModel):
    """
    What the Dashboard receives to display the table.
    Matches the columns in models.Transaction
    """
    id: int
    date: datetime
    amount: Optional[float]
    merchant: Optional[str]
    category: str
    bank_name: Optional[str]
    
    # Status Flags for the UI
    status: str  # 'CLEAN', 'PENDING_REVIEW', 'DISCARDED'
    is_potential_duplicate: bool
    raw_email_body: Optional[str] # For the 'View Email' popup

    class Config:
        orm_mode = True # Essential for SQLAlchemy compatibility