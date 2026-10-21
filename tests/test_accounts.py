from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_get_accounts_empty_or_list():
    response = client.get("/accounts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_account():
    payload = {
        "name": "Test Checking Account",
        "account_type": "checking",
        "current_balance": 1000.0
    }
    response = client.post("/accounts", json=payload)
    assert response.status_code == 201
    data = response.json()
    
    assert data["name"] == "Test Checking Account"
    assert data["account_type"] == "checking"
    assert data["current_balance"] == 1000.0
    assert "id" in data