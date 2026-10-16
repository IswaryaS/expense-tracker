import io
import json
import pytest
from unittest.mock import AsyncMock, patch
from datetime import date

import respx
import httpx
from backend.main import extract_bill_data_with_groq


def test_read_bills_empty(client):
    response = client.get("/bills/review")
    assert response.status_code == 200
    assert response.json() == []


def test_update_bill_status(client, session):
    from backend.models import Bill

    # 1. Manually insert a mock pending bill into the test database
    db_bill = Bill(bill_date=date(2026, 3, 17),
                   vendor_name="Acme Corp", total_amount=50.0, status="pending", reviewer_comment=None)
    session.add(db_bill)
    session.commit()
    session.refresh(db_bill)

    # 2. Fire a PUT request using the test client to approve it
    payload = {
        "bill_date": "2026-03-17",
        "vendor_name": "Acme Corp",
        "total_amount": 50.0,
        "category": "Utilities",
        "status": "approved",
        "reviewer_comment": "Verified manually"
    }
    response = client.put(f"/bills/{db_bill.id}", json=payload)

    # 3. Assertions: Verify backend behavior matches expectations
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["reviewer_comment"] == "Verified manually"
    # Ensures your timestamp automation worked!
    assert data["reviewed_at"] is not None

# <-- Import your actual function here


@pytest.mark.asyncio  # Required for async test loops
@respx.mock           # Automatically intercepts all httpx requests in this test
async def test_extract_data_from_groq():
    mock_groq_content = {
        "bill_date": "2026-03-17",
        "vendor_name": "Groq Mocked Vendor",
        "total_amount": 250.75
    }
    # 1. Setup the mock URL and what it should return
    # This targets any POST request hitting the Groq completions endpoint
    groq_mock = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(mock_groq_content)
                        }
                    }
                ]
            }
        )
    )

    mock_image_file = io.BytesIO(b"mock-image-binary-bytes")

    # 2. Call your actual function (which uses standard httpx.AsyncClient internally)
    result = await extract_bill_data_with_groq(image_bytes=mock_image_file.getvalue())

    # 3. Assertions
    assert groq_mock.called is True
    # Adjust this assertion based on what your wrapper function actually extracts/returns
    assert result["vendor_name"] == "Groq Mocked Vendor"
    assert result["total_amount"] == 250.75
    assert result["bill_date"] == "2026-03-17"


def test_upload_bill(client):
    """
    Verifies that the /bills/upload endpoint cleanly accepts multipart file payloads,
    intercepts the external Groq network request, and saves a pending record.
    """

    # 1. Patch the exact module path where your FastAPI endpoint *imports* the function
    with patch("backend.main.extract_bill_data_with_groq", new_callable=AsyncMock) as mock_extract_from_groq:

        # Structure the mock data that your prompt typically instructs Groq to output
        mock_extract_from_groq.return_value = {
            "bill_date": "2026-03-17",
            "vendor_name": "Groq Mocked Vendor",
            "total_amount": 250.75
        }

        # Simulate an image file uploading via multipart form-data
        mock_image_file = io.BytesIO(b"mock-image-binary-bytes")
        payload_files = {"file": mock_image_file}

        # Trigger the POST endpoint
        response = client.post("/bills/upload", files=payload_files)

        # 5. Assertions: Confirm network structures and field updates flow seamlessly
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["vendor_name"] == "Groq Mocked Vendor"
        assert response_data["total_amount"] == 250.75
        assert response_data["category"] == "Miscellaneous"
        # Should default to pending validation state
        assert response_data["status"] == "pending"
        # Verifies row successfully committed to SQLite
        assert response_data["id"] is not None

        mock_extract_from_groq.assert_called_once()
