from pydantic import BaseModel, ConfigDict
from typing import Optional

class CategoryBase(BaseModel):
    name: str
    color: str = "#94a3b8"
    is_income: bool = False

class CategoryOut(CategoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class CategoryCreate(BaseModel):
    name: str
    is_income: bool = False
    color: Optional[str] = None