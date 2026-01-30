from pydantic import BaseModel
from typing import List, Optional
from .transactions import TransactionOut

class DuplicateGroup(BaseModel):
    group_id: str
    confidence_score: int
    transactions: List[TransactionOut]
    warning_message: str

class ResolveDuplicate(BaseModel):
    txn1_id: int
    txn2_id: int
    keep_id: Optional[int] = None
    delete_id: Optional[int] = None