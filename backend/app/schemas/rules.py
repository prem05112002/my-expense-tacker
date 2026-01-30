from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import date

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