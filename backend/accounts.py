from typing import List
from sqlmodel import Session, select
from fastapi import APIRouter, Depends

from backend.database import get_session
from backend.models import Account

router = APIRouter(prefix="/accounts", tags=["Accounts"])

@router.get("", response_model=List[Account])
def get_accounts(session: Session = Depends(get_session)):
    """Retrieve all financial accounts (checking, savings, credit cards)."""
    accounts = session.exec(select(Account)).all()
    return accounts

@router.post("", status_code=201, response_model=Account)
def create_account(account: Account, session: Session = Depends(get_session)):
    """Optional: Create a new account if none exist yet."""
    session.add(account)
    session.commit()
    session.refresh(account)
    return account