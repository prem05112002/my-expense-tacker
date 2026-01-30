from pydantic import BaseModel, ConfigDict, field_validator
from typing import List

class UserSettingsUpdate(BaseModel):
    salary_day: int
    budget_type: str 
    budget_value: float
    # These match the frontend "MultiSelect"
    ignored_categories: List[str] = []   
    income_categories: List[str] = []    
    view_cycle_offset: int = 0

class UserSettingsOut(BaseModel):
    id: int
    salary_day: int
    budget_type: str
    budget_value: float
    monthly_budget: float
    view_cycle_offset: int
    
    # ✅ OUTPUTS AS LISTS
    ignored_categories: List[str]
    income_categories: List[str]

    @field_validator('ignored_categories', 'income_categories', mode='before')
    @classmethod
    def convert(cls, v):
        return parse_db_string_to_list(v)

    model_config = ConfigDict(from_attributes=True)

def parse_db_string_to_list(v: Any) -> List[str]:
    """Force conversion of DB string 'A,B' to List ['A','B']"""
    if isinstance(v, str):
        return [x.strip() for x in v.split(',')] if v.strip() else []
    if isinstance(v, list):
        return v
    return []