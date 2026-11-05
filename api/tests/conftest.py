import sys
from pathlib import Path

# Let tests import app.py from the api/ folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as api_module
import pytest


@pytest.fixture
def client(monkeypatch):
    """A test client for the api. The database address can never resolve (.invalid)."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:pass@db.invalid:5432/freshtrack"
    )
    return api_module.create_app().test_client()
