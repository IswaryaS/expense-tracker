from enum import Enum
from typing import Optional
from datetime import date, datetime
from unicodedata import category
from sqlmodel import SQLModel, Field
from pydantic import BaseModel

# --------------------------------------------------------------
#  Enums & DB model
# --------------------------------------------------------------


class BillStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

# Define an Enum for cleaner category handling and validation


class BillCategory(str, Enum):
    utilities = "Utilities"
    groceries = "Groceries"
    miscellaneous = "Miscellaneous"


class Bill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    bill_date: date
    vendor_name: str
    total_amount: float

    category: BillCategory = Field(
        default=BillCategory.miscellaneous, index=True)
    status: BillStatus = Field(default=BillStatus.pending, index=True)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    reviewer_comment: Optional[str] = None

    class Config:
        from_attributes = True

# --------------------------------------------------------------
#  Pydantic response model (used for OpenAPI docs)
# --------------------------------------------------------------


class BillResponse(BaseModel):
    id: int
    bill_date: date
    vendor_name: str
    total_amount: float
    status: BillStatus
    extracted_at: datetime

    class Config:
        from_attributes = True

# A clean payload schema for updating bills


class BillUpdate(BaseModel):
    bill_date: Optional[date] = None
    vendor_name: Optional[str] = None
    total_amount: Optional[float] = None
    category: Optional[BillCategory] = None
    status: Optional[BillStatus] = None
    reviewed_at: Optional[date] = None
    reviewer_comment: Optional[str] = None
