import os
import tempfile

import pytest

import database.db as db_module
from app import app as flask_app


@pytest.fixture
def app(monkeypatch, tmp_path):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "_DB_PATH", str(test_db))

    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"

    with flask_app.app_context():
        db_module.init_db()

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()