# --------------------------------------------------------------
#  expense_tracker/main.py
# --------------------------------------------------------------

from fastapi import APIRouter, FastAPI

from .routers.statements import router as statement_router
from .routers.accounts import router as account_router
from .routers.bills import router as bill_router

# --------------------------------------------------------------
#  FastAPI app
# --------------------------------------------------------------
app = FastAPI(title="Expense Tracker (Groq OCR)")
router = APIRouter()
app.include_router(bill_router)
app.include_router(statement_router)
app.include_router(account_router)
