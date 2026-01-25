from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import date

# --- RESPONSE MODELS (Data sent TO Frontend) ---

class Transaction(BaseModel):
    id: int
    bank_name: Optional[str]
    amount: float
    payment_mode: Optional[str]
    merchant_name: Optional[str]
    txn_date: Optional[date]
    category_id: Optional[int]
    category_name: Optional[str] = "Uncategorized"
    category_color: Optional[str] = "#cbd5e1"

class DashboardStats(BaseModel):
    total_spend: float
    uncategorized_count: int
    recent_transactions: List[Transaction]
    category_breakdown: List[dict] # Format: {name: "Food", value: 500, fill: "#red"}

# --- REQUEST MODELS (Data received FROM Frontend) ---

class CategorizeRequest(BaseModel):
    transaction_ids: List[int]     # Supports bulk updates
    category_id: int
    
    # The "Smart" Features
    create_rule: bool = False      # "Remember this merchant?"
    rule_keyword: Optional[str] = None
    apply_retroactive: bool = False # "Apply to past transactions?"