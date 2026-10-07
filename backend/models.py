from enum import Enum
from typing import Optional, List
from datetime import date, datetime
from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel, ConfigDict

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

    # 🌟 NEW EXTENSION FIELD: Connects a physical paper bill to a cleared bank row when paid
    transaction_id: Optional[int] = Field(
        default=None, foreign_key="transaction.id", nullable=True)
    transaction: Optional["Transaction"] = Relationship(
        back_populates="linked_bills")

    model_config = ConfigDict(from_attributes=True)

# --------------------------------------------------------------
#  Pydantic response model (used for OpenAPI docs)
# --------------------------------------------------------------


class BillResponse(BaseModel):
    id: int
    bill_date: date
    vendor_name: str
    total_amount: float
    category: BillCategory
    status: BillStatus
    extracted_at: datetime
    reviewer_comment: Optional[str]
    reviewed_at: Optional[datetime]
    transaction_id: Optional[int]

    model_config = ConfigDict(from_attributes=True)

# A clean payload schema for updating bills


class BillUpdate(BaseModel):
    bill_date: Optional[date] = None
    vendor_name: Optional[str] = None
    total_amount: Optional[float] = None
    category: Optional[BillCategory] = None
    status: Optional[BillStatus] = None
    reviewed_at: Optional[date] = None
    reviewer_comment: Optional[str] = None
    transaction_id: Optional[int] = None

# ==============================================================
# 2. 🌟 NEW BANK & ACCOUNT SCHEMAS (For Ingestion & Analytics)
# ==============================================================


class AccountType(str, Enum):
    checking = "checking"
    savings = "savings"
    credit_card = "credit_card"


class TransactionSource(str, Enum):
    bank_statement = "bank_statement"
    manual = "manual"


class Account(SQLModel, table=True):
    """Represents a real-world financial destination (e.g., Chase Checking, Amex Gold)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)  # e.g., "Chase Total Checking"
    account_type: AccountType
    current_balance: float = Field(default=0.0)

    # Relationship: One account houses many transaction records
    transactions: List["Transaction"] = Relationship(back_populates="account")

    model_config = ConfigDict(from_attributes=True)


class Transaction(SQLModel, table=True):
    """The central source of financial truth. Handles income, expenses, and automated imports."""
    id: Optional[int] = Field(default=None, primary_key=True)
    booking_date: date = Field(index=True)
    description: str  # Raw description parsed from statement

    # 🪙 Accounting signs: Positive (+) = Income/Credits | Negative (-) = Expenses/Debits
    amount: float

    category: str = Field(default="Uncategorized", index=True)
    source: TransactionSource = Field(default=TransactionSource.bank_statement)

    # Foreign Keys & Relationships
    account_id: int = Field(foreign_key="account.id", index=True)
    account: Account = Relationship(back_populates="transactions")

    # Relationship back to physical paper bills (one transaction could settle multiple bills)
    linked_bills: List[Bill] = Relationship(back_populates="transaction")

    model_config = ConfigDict(from_attributes=True)


class TransactionExtractItem(BaseModel):
    booking_date: date = Field(description="The transaction execution date strictly formatted as YYYY-MM-DD")
    description: str = Field(description="The full clean description or vendor name of the transaction")
    amount: float = Field(description="The financial value. Positive for deposits/credits, negative for withdrawals/debits.")

class ExtractedStatementPayload(BaseModel):
    transactions: List[TransactionExtractItem] = Field(default=[], description="List of all extracted ledger transactions")