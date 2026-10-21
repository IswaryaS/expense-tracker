from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlmodel import Session

from ..database import get_session
from ..models import ExtractedStatementPayload, Account, Transaction, TransactionSource
from ..services.ai_analyzer import groq_analyze_statement
from ..services.pdf_parser import extract_transaction_pages, NoTransactionsFoundError

router = APIRouter(prefix="/accounts")

@router.post("/upload-statement/{account_id}", status_code=201)
async def upload_bank_statement(
    account_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """
    Processes an uploaded statement PDF, extracts rows via PyMuPDF + Groq,
    and commits them to the database for a specific destination Account.
    """
        # 1. Fetch the account; dynamically create it if it is a new/unrecognized ID
    account = session.get(Account, account_id)
    
    if not account:
        # Dynamically instantiate a new account record for the user
        account = Account(
            id=account_id,
            name=f"Auto-Generated Account #{account_id}",
            account_type="checking",  # Safe default string fallback matching your Enum
            current_balance=0.0
        )
        try:
            session.add(account)
            session.commit()
            session.refresh(account)
        except Exception as db_init_err:
            session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to auto-create missing account destination: {str(db_init_err)}"
            )

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400, detail="Invalid file format. Please upload a native PDF."
        )

    # 2. Extract and pre-filter pages using PyMuPDF helper
    pdf_data = await file.read()
    try:
        raw_ledger_text = extract_transaction_pages(pdf_data)
    except NoTransactionsFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF parsing breakdown: {str(e)}")

    # ----
    # Temporary debug return placed right after step 2 (extract_transaction_pages)
    # return {
    #    "filename": file.filename,
    #    "debug_raw_extracted_text": raw_ledger_text
    # }
    # ----

    validated_payload = await groq_analyze_statement(raw_ledger_text)

    # 6. Map models directly to database layer entities
    db_transactions = []
    running_balance_modifier = 0.0

    for item in validated_payload.transactions:
        # Instantiating your strict SQLModel schema object definition
        db_transaction = Transaction(
            booking_date=item.booking_date,
            description=item.description,
            amount=item.amount,
            category="Uncategorized",
            source=TransactionSource.bank_statement,
            account_id=account.id
        )
        db_transactions.append(db_transaction)
        running_balance_modifier += item.amount

    # 7. Atomically save records and update the target account balance
    try:
        session.add_all(db_transactions)
        
        # Keep current balance field accurate on the account tracking parent model
        account.current_balance += running_balance_modifier
        session.add(account)
        
        session.commit()
    except Exception as db_err:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database transaction failure. Rolling back operations. Error: {str(db_err)}"
        )

    return {
            "status": "success",
            "account_id": account.id,
            "account_new_balance": account.current_balance,
            "transactions_imported_count": len(db_transactions),
            # Include the list of transactions so Streamlit can render the st.data_editor
            "transactions": [
                {
                    "id": tx.id,
                    "booking_date": tx.booking_date,
                    "description": tx.description,
                    "amount": tx.amount,
                    "category": tx.category
                } for tx in db_transactions
            ]
        }

@router.put("/{account_id}/transactions/batch", status_code=201)
async def save_batch_transactions(
    account_id: int, 
    payload: ExtractedStatementPayload, 
    session: Session = Depends(get_session)
):
    """Save a batch of verified transactions extracted from a bank statement."""
    # Verify account exists
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    saved_count = 0
    for item in payload.transactions:
        db_transaction = Transaction(
            booking_date=item.booking_date,
            description=item.description,
            amount=item.amount,
            account_id=account_id,
            source=TransactionSource.bank_statement,
            category="Uncategorized" # You can add auto-categorization here later if desired
        )
        session.add(db_transaction)
        saved_count += 1

    session.commit()
    return {"message": f"Successfully saved {saved_count} transactions.", "account_id": account_id}
