# --------------------------------------------------------------
#  expense_tracker/main.py
# --------------------------------------------------------------
import base64
import os
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select
from dotenv import load_dotenv

# --------------------------------------------------------------
#  Load environment (Groq API key)
# --------------------------------------------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not found – set it in a .env file or the environment")

# --------------------------------------------------------------
#  FastAPI app
# --------------------------------------------------------------
app = FastAPI(title="Expense Tracker (Groq OCR)")

# --------------------------------------------------------------
#  SQLite DB (for the prototype)
# --------------------------------------------------------------
sqlite_file = "bills.db"
sqlite_url = f"sqlite:///{sqlite_file}"
engine = create_engine(sqlite_url, echo=False)

# --------------------------------------------------------------
#  Enums & DB model
# --------------------------------------------------------------


class BillStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Bill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    vendor_name: str
    total_amount: float

    status: BillStatus = Field(default=BillStatus.pending, index=True)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    reviewer_comment: Optional[str] = None


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)

# --------------------------------------------------------------
#  Pydantic response model (used for OpenAPI docs)
# --------------------------------------------------------------


class BillResponse(BaseModel):
    id: int
    date: date
    vendor_name: str
    total_amount: float
    status: BillStatus
    extracted_at: datetime

    class Config:
        orm_mode = True

# --------------------------------------------------------------
#  Dependency – new Session per request
# --------------------------------------------------------------


def get_session():
    with Session(engine) as session:
        yield session


# --------------------------------------------------------------
#  Groq OCR helper
# --------------------------------------------------------------
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
# replace with the exact vision model you have
GROQ_MODEL = "llama-3.2-vision-90b"


async def extract_bill_data_with_groq(image_bytes: bytes) -> dict:
    """Send image to Groq Vision model and return a dict with date, vendor_name, total_amount."""
    b64_image = base64.b64encode(image_bytes).decode()
    data_url = f"data:image/jpeg;base64,{b64_image}"

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an OCR assistant. Extract the **date**, **vendor name** "
                    "and **total amount** from the attached receipt image. "
                    "Return a **valid JSON object** with exactly the keys: "
                    "`date`, `vendor_name`, `total_amount`. "
                    "Date must be ISO‑8601 (YYYY‑MM‑DD). Amount is a number (float)."
                ),
            },
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": data_url}}],
            },
        ],
        "temperature": 0.0,
        "max_tokens": 256,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GROQ_ENDPOINT, json=payload, headers=headers)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Groq API error {resp.status_code}: {resp.text}",
        )

    data = resp.json()
    try:
        raw_text = data["choices"][0]["message"]["content"]
        # Groq may return the JSON with surrounding backticks or extra text.
        # We'll try to locate the first `{` and the matching `}`.
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        json_str = raw_text[start:end]
        # safe because we control the prompt & model is deterministic
        extracted = eval(json_str)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse Groq response: {exc}",
        )

    # Minimal validation – make sure all three keys exist
    required_keys = {"date", "vendor_name", "total_amount"}
    if not required_keys.issubset(extracted):
        raise HTTPException(
            status_code=422,
            detail=f"Groq response missing required keys. Got: {list(extracted.keys())}",
        )
    return extracted
