from pydantic import BaseModel
from typing import Any, List, Optional
from datetime import date


class SmartSearchFilters(BaseModel):
    """Structured filters parsed from natural language query."""
    categories: Optional[List[str]] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    payment_type: Optional[str] = None
    merchant_pattern: Optional[str] = None
    is_smart_search: bool = True


class SmartSearchRequest(BaseModel):
    """Request body for smart search endpoint."""
    query: str
    page: int = 1
    limit: int = 15
    sort_by: str = "txn_date"
    sort_order: str = "desc"


class SmartSearchResponse(BaseModel):
    """Response from smart search including parsed filters."""
    data: List[Any]
    total: int
    page: int
    limit: int
    total_pages: int
    debit_sum: float = 0.0
    credit_sum: float = 0.0
    parsed_filters: SmartSearchFilters
    search_type: str  # 'smart' or 'fuzzy'

    class Config:
        from_attributes = True
