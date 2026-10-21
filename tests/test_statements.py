import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from datetime import date
from backend.main import app
from backend.models import ExtractedStatementPayload, TransactionExtractItem

client = TestClient(app)

@patch("backend.routers.statements.groq_analyze_statement")  # Adjust path to where your router imports the AI analyzer
@patch("backend.routers.statements.extract_transaction_pages") # Adjust path to where your router imports the PDF parser
def test_upload_statement_success(mock_pdf_parser, mock_ai_analyzer):
    # 1. Arrange: Mock the PDF reader text extraction
    mock_pdf_parser.return_value = "Mocked extracted text from relevant statement pages"

    # 2. Arrange: Mock the LLM / Groq structured response
    mock_ai_analyzer.return_value = ExtractedStatementPayload(
        transactions=[
            TransactionExtractItem(
                booking_date=date(2026, 6, 1),
                description="Supermarket Purchase",
                amount=-54.20
            )
        ]
    )

    # 3. Act: Simulate uploading a PDF file to account ID 1
    response = client.post(
        "/accounts/upload-statement/1",
        files={"file": ("sample_statement.pdf", b"%PDF-1.4 fake pdf binary content", "application/pdf")}
    )

    # 4. Assert: Verify status code and payload structure returned to Streamlit
    assert response.status_code == 201
    data = response.json()
    
    assert data["status"] == "success"
    assert data["account_id"] == 1
    assert data["transactions_imported_count"] == 1
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["description"] == "Supermarket Purchase"
    assert data["transactions"][0]["amount"] == -54.20

    from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_save_batch_transactions_success():
    # 1. First, create a valid target account
    account_res = client.post("/accounts", json={
        "name": "Batch Test Account",
        "account_type": "savings",
        "current_balance": 500.0
    })
    account_id = account_res.json()["id"]

    # 2. Payload matching your ExtractedStatementPayload / batch format
    payload = {
        "transactions": [
            {
                "booking_date": "2026-06-01",
                "description": "Grocery Store",
                "amount": -45.50
            },
            {
                "booking_date": "2026-06-02",
                "description": "Salary Deposit",
                "amount": 2500.0
            }
        ]
    }

    # 3. Send batch save request (adjust route method/path to match your implementation)
    response = client.put(f"/accounts/{account_id}/transactions/batch", json=payload)
    
    assert response.status_code in [200, 201]
    data = response.json()
    assert data["account_id"] == account_id

def test_save_batch_transactions_account_not_found():
    # Try saving to a non-existent account ID
    payload = {
        "transactions": [
            {
                "booking_date": "2026-06-01",
                "description": "Ghost Store",
                "amount": -10.00
            }
        ]
    }
    response = client.put("/accounts/99999/transactions/batch", json=payload)
    assert response.status_code == 404