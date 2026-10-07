import os
import httpx
import pymupdf

from dotenv import load_dotenv
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlmodel import Session
from pydantic import ValidationError
from typing import List

from backend.database import get_session
from backend.models import ExtractedStatementPayload, Account, Transaction, TransactionSource

router = APIRouter(prefix="/api")

# Tuned heuristics for high-signal financial tables
TRANSACTION_KEYWORDS = ["ledger", "date", "description", "withdrawal", "deposit", "balance"]
LEGAL_EXCLUSIONS = ["terms and conditions", "error resolution", "disclosure statement", "fee schedule"]

class NoTransactionsFoundError(ValueError):
    """Custom exception raised when a PDF lacks matching transaction layout structures."""
    pass

def extract_transaction_pages(pdf_bytes: bytes) -> str:
    """
    Opens a raw PDF file from memory, extracts text using layout block sorting 
    to preserve tabular rows, and filters out legal boilerplate pages.
    """
    # Load the document dynamically from memory
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    compiled_text: List[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # 1. Row-Preserving Extraction: Sort text blocks top-to-bottom, left-to-right
        # This prevents multi-column layouts from overlapping columns during extraction
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (b[1], b[0])) # Sort by Y coordinate first, then X coordinate
        
        # Assemble string representation for page classification
        page_text = "\n".join([b[4] for b in blocks if b[4].strip()])
        page_text_lower = page_text.lower()

        # 2. Strict Filter Execution
        # If it looks like a boilerplate legal index page, bypass entirely
        if any(exclusion in page_text_lower for exclusion in LEGAL_EXCLUSIONS):
            continue

        # Check if the text matches target ledger indicators
        if any(keyword in page_text_lower for keyword in TRANSACTION_KEYWORDS):
            compiled_text.append(f"### START OF STATEMENT PAGE {page_num + 1} ###")
            compiled_text.append(page_text.strip())
            compiled_text.append(f"### END OF STATEMENT PAGE {page_num + 1} ###\n")

    doc.close()

    if not compiled_text:
        raise NoTransactionsFoundError(
            "No matching transaction ledger patterns were discovered in this document."
        )

    return "\n".join(compiled_text)

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not found – set it in a .env file or the environment")

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "qwen/qwen3.8-27b"

# Define a strict system instruction prompt
GROQ_SYSTEM_PROMPT = """
You are an expert financial data extraction engine. 
Your task is to extract structured transaction data from raw bank statement text and return a single JSON object.

You MUST follow this output structure format exactly:
{
  "transactions": [
    {
      "booking_date": "YYYY-MM-DD",
      "description": "Clean description or vendor name",
      "amount": -54.20
    }
  ]
}

Extraction Guidelines:
1. Identify all booking_date, description, and amount values.
2. Format all dates strictly as strings matching the 'YYYY-MM-DD' ISO pattern.
3. Mark all withdrawals/debits as negative floats (e.g., -54.20). Mark all deposits/credits as positive floats (e.g., 1200.00).
4. Do not include currency symbols or structural formatting commas within the floats.
"""


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

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": (GROQ_SYSTEM_PROMPT)},
            {"role": "user", "content": f"Here is the raw bank statement text layout:\n\n{raw_ledger_text}"}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }

    # 4. Asynchronous request handling via httpx
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            raw_json_response = response.json()["choices"][0]["message"]["content"]
        except Exception as net_err:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to communicate with remote Groq framework: {str(net_err)}"
            )

    # 5. Parse and Validate the extracted payload structure 
    try:
        validated_payload = ExtractedStatementPayload.model_validate_json(raw_json_response)
    except ValidationError as val_err:
        raise HTTPException(
            status_code=502, 
            detail=f"LLM generated an invalid structural database schema: {str(val_err)}"
        )

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
        "transactions_imported_count": len(db_transactions)
    }
