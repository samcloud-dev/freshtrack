import sys
from pathlib import Path

# Let tests import app.py from the web/ folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as web_module
import pytest
from api_client import ApiUnavailable


class FakeApi:
    """Stands in for the real api, so page tests need no network."""

    def __init__(self):
        self.items = []
        self.ready = True
        self.add_errors = {}
        self.close_outcome = "closed"
        self.down = False
        self.added = []
        self.closed = []
        self.closed_items = []
        self.update_outcome = ("updated", {})
        self.updated = []

    def _check(self):
        if self.down:
            raise ApiUnavailable

    def is_ready(self):
        return self.ready

    def list_items(self):
        self._check()
        return self.items

    def add_item(self, fields):
        self._check()
        self.added.append(fields)
        if self.add_errors:
            return None, self.add_errors
        return {"id": 99, **fields}, {}

    def close_item(self, item_id, status):
        self._check()
        self.closed.append((item_id, status))
        return self.close_outcome

    def list_closed_items(self):
        self._check()
        return self.closed_items

    def get_item(self, item_id):
        self._check()
        for item in self.items + self.closed_items:
            if item["id"] == item_id:
                return item
        return None

    def update_item(self, item_id, fields):
        self._check()
        self.updated.append((item_id, fields))
        return self.update_outcome


@pytest.fixture
def fake_api():
    return FakeApi()


@pytest.fixture
def app(monkeypatch, fake_api):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret")
    # The address never resolves (.invalid); the fake replaces the client anyway.
    monkeypatch.setenv("API_URL", "http://api.invalid")
    # The test client talks plain http, so the cookie must not require HTTPS here.
    monkeypatch.setenv("COOKIE_SECURE", "false")
    flask_app = web_module.create_app()
    flask_app.config["API"] = fake_api
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf(client):
    """A valid form token, the same way a real page gets one."""
    with client.session_transaction() as session:
        session["csrf"] = "test-token"
    return "test-token"
