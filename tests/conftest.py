import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
from backend.main import app
from backend.database import get_session

import backend.schemas

# Create a clean, separate in-memory database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={
                       "check_same_thread": False},
                       poolclass=StaticPool)


@pytest.fixture(name="session")
def session_fixture():
    # Setup: Create tables
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    # Teardown: Clean up tables after the test finishes
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):

    app.dependency_overrides[get_session] = lambda: session

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
