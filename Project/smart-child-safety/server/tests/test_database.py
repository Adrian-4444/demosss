"""Tests for database connectivity and session lifecycle."""

from sqlalchemy import text
from app.database import check_db_connection, get_db


def test_database_connection_checker():
    """Verify that check_db_connection successfully connects and runs SELECT 1."""
    assert check_db_connection() is True


def test_get_db_yields_session():
    """Verify that get_db dependency yields a live session and closes without leak."""
    db_gen = get_db()
    session = next(db_gen)
    try:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass
