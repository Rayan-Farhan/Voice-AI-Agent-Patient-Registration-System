import os

# Point the app at an in-memory database before any app module is imported:
# app.db builds its engine from this at import time.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import Base
from app.main import app as fastapi_app


@pytest.fixture
def db_session():
    """A throwaway in-memory database per test.

    StaticPool keeps every connection pointed at the same in-memory database;
    without it SQLite hands each connection a separate empty one.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def valid_patient():
    return {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "1985-03-12",
        "sex": "Female",
        "phone_number": "(415) 555-0142",
        "address_line_1": "1200 Market Street",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94102",
    }
