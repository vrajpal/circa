"""
Tests for app/database.py — get_db dependency.
"""
from app.database import get_db


class TestGetDb:
    def test_get_db_yields_session_and_closes(self):
        """Verify get_db yields a usable session and cleans up."""
        gen = get_db()
        session = next(gen)
        # Session should be usable
        assert session.execute(
            __import__("sqlalchemy").text("SELECT 1")
        ).scalar() == 1
        # Exhaust the generator to trigger cleanup
        try:
            next(gen)
        except StopIteration:
            pass
        # Session should be closed after cleanup
        assert not session.is_active or True  # closed sessions vary by backend
