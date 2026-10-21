import os
import httpx
import base64

from dotenv import load_dotenv
from fastapi import HTTPException
from pydantic import ValidationError

from ..models import ExtractedStatementPayload

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not found – set it in a .env file or the environment")


# --------------------------------------------------------------
#  Groq OCR helper
# --------------------------------------------------------------
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
# replace with the exact vision model you have
GROQ_MODEL = "qwen/qwen3.8-27b"


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
                    "`bill_date`, `vendor_name`, `total_amount`. "
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
    required_keys = {"bill_date", "vendor_name", "total_amount"}
    if not required_keys.issubset(extracted):
        raise HTTPException(
            status_code=422,
            detail=f"Groq response missing required keys. Got: {list(extracted.keys())}",
        )
    return extracted

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

async def groq_analyze_statement(raw_ledger_text):
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

    return validated_payload
