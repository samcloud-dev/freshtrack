"""Tests against a real PostgreSQL. Skipped unless TEST_DATABASE_URL is set.

Use a throwaway database only. Each test runs in its own new PostgreSQL schema
(a separate namespace inside the database), which is dropped afterwards.
"""

import os
import uuid
from datetime import date

import db
import psycopg
import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture
def url():
    schema = "ft_test_" + uuid.uuid4().hex[:12]
    with psycopg.connect(TEST_URL, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    joiner = "&" if "?" in TEST_URL else "?"
    # Every connection made with this URL uses only the test schema.
    yield f"{TEST_URL}{joiner}options=-csearch_path%3D{schema}"
    with psycopg.connect(TEST_URL, autocommit=True) as conn:
        conn.execute(f'DROP SCHEMA "{schema}" CASCADE')


def new_item(name, label_date, **changes):
    item = {
        "name": name,
        "quantity": "1",
        "location": "fridge",
        "label_date": label_date,
        "date_type": "best_before",
    }
    item.update(changes)
    return item


def test_schema_can_be_applied_twice(url):
    db.ensure_schema(url)
    db.ensure_schema(url)


def test_create_and_list_soonest_first(url):
    db.ensure_schema(url)
    db.create_item(url, new_item("milk", date(2026, 11, 8)))
    db.create_item(url, new_item("yogurt", date(2026, 11, 5)))
    db.create_item(url, new_item("cheese", date(2026, 11, 5)))
    names = [i["name"] for i in db.list_active_items(url)]
    # Same date: the one added first comes first.
    assert names == ["yogurt", "cheese", "milk"]


def test_new_item_starts_active(url):
    db.ensure_schema(url)
    item = db.create_item(url, new_item("milk", date(2026, 11, 8)))
    assert item["status"] == "active"
    assert item["closed_at"] is None
    assert item["created_at"] is not None


def test_closed_item_leaves_list_but_stays_in_database(url):
    db.ensure_schema(url)
    item = db.create_item(url, new_item("milk", date(2026, 11, 8)))
    outcome, closed = db.close_item(url, item["id"], "used")
    assert outcome == "closed"
    assert closed["status"] == "used" and closed["closed_at"] is not None
    assert db.list_active_items(url) == []
    with db.connect(url) as conn:
        kept = conn.execute(
            "SELECT status FROM items WHERE id = %s", (item["id"],)
        ).fetchone()
    assert kept == {"status": "used"}


def test_closing_twice_does_not_change_it(url):
    db.ensure_schema(url)
    item = db.create_item(url, new_item("milk", date(2026, 11, 8)))
    db.close_item(url, item["id"], "discarded")
    outcome, existing = db.close_item(url, item["id"], "used")
    assert outcome == "already_closed"
    assert existing["status"] == "discarded"


def test_closing_unknown_item(url):
    db.ensure_schema(url)
    assert db.close_item(url, 999, "used") == ("not_found", None)


@pytest.mark.parametrize(
    "changes",
    [{"location": "garage"}, {"date_type": "expiry"}, {"name": "  "}, {"quantity": ""}],
)
def test_database_rejects_bad_values_on_its_own(url, changes):
    # Second line of defence: even if validation were skipped, the table refuses bad data.
    db.ensure_schema(url)
    item = new_item("milk", date(2026, 11, 8))
    item.update(changes)  # swap in the one bad value
    with pytest.raises(psycopg.errors.CheckViolation):
        db.create_item(url, item)


def test_database_rejects_active_item_with_closed_time(url):
    db.ensure_schema(url)
    item = db.create_item(url, new_item("milk", date(2026, 11, 8)))
    with pytest.raises(psycopg.errors.CheckViolation), db.connect(url) as conn:
        conn.execute("UPDATE items SET closed_at = now() WHERE id = %s", (item["id"],))
