"""Shared fixtures for backend tests."""

import pytest

from backend.app.db.connection import connect, init_db


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    init_db(conn)
    yield conn, db_path
    conn.close()


@pytest.fixture
def tmp_uploads(tmp_path):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    return uploads
