"""Pytest fixtures and test environment configuration."""

import os
import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

# Set testing environment before importing app
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///./test_temp.db"
os.environ["LOG_LEVEL"] = "WARNING"

import app.models  # Import all models to ensure complete metadata
from app.config import get_settings
from app.database import Base, engine
from app.main import app

# Enforce foreign key constraints in SQLite during tests
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if engine.url.drivername.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create test tables before test session and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_temp.db"):
        try:
            os.remove("./test_temp.db")
        except OSError:
            pass


@pytest.fixture
def client():
    """Synchronous test client fixture backed by Starlette TestClient."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Per-test database session with automatic transaction rollback."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
