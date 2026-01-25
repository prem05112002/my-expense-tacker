from pydantic import BaseModel

class ResolveDuplicateRequest(BaseModel):
    txn_id: int
    action: str 

class UnmatchedActionRequest(BaseModel):
    uid: str
    action: str