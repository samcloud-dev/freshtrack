"""Route tests: the database functions are replaced by fakes, so no PostgreSQL is needed.
The real SQL is tested in test_db_integration.py."""

from datetime import UTC, date, datetime

import app as api_module
import psycopg
import pytest

CREATED = datetime(2026, 11, 3, 22, 0, tzinfo=UTC)


def row(**changes):
    item = {
        "id": 1,
        "name": "Greek yogurt",
        "quantity": "2 cartons",
        "location": "fridge",
        "label_date": date(2026, 11, 6),
        "date_type": "best_before",
        "status": "active",
        "created_at": CREATED,
        "closed_at": None,
    }
    item.update(changes)
    return item


NEW_ITEM = {
    "name": "Greek yogurt",
    "quantity": "2 cartons",
    "location": "fridge",
    "label_date": "2026-11-06",
    "date_type": "best_before",
}


def test_list_items_returns_active_items_as_json(client, monkeypatch):
    monkeypatch.setattr(api_module.db, "list_active_items", lambda url: [row()])
    response = client.get("/items")
    assert response.status_code == 200
    assert response.get_json() == {
        "items": [
            {
                "id": 1,
                "name": "Greek yogurt",
                "quantity": "2 cartons",
                "location": "fridge",
                "label_date": "2026-11-06",
                "date_type": "best_before",
                "status": "active",
                "created_at": "2026-11-03T22:00:00+00:00",
                "closed_at": None,
            }
        ]
    }


def test_list_items_empty(client, monkeypatch):
    monkeypatch.setattr(api_module.db, "list_active_items", lambda url: [])
    response = client.get("/items")
    assert response.status_code == 200
    assert response.get_json() == {"items": []}


def test_add_item_saves_cleaned_item(client, monkeypatch):
    saved = {}

    def fake_create(url, item):
        saved.update(item)
        return row()

    monkeypatch.setattr(api_module.db, "create_item", fake_create)
    response = client.post("/items", json=NEW_ITEM)
    assert response.status_code == 201
    assert response.get_json()["id"] == 1
    assert saved["label_date"] == date(2026, 11, 6)


def test_add_item_rejects_bad_input_without_touching_database(client, monkeypatch):
    def must_not_run(url, item):
        raise AssertionError("database should not be called")

    monkeypatch.setattr(api_module.db, "create_item", must_not_run)
    response = client.post("/items", json={**NEW_ITEM, "location": "garage"})
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": {"location": "Must be one of: fridge, freezer, cupboard."}
    }


def test_add_item_rejects_non_json_body(client):
    response = client.post("/items", data="name=yogurt")
    assert response.status_code == 400
    assert response.get_json() == {"errors": {"body": "Send a JSON object."}}


def test_mark_item_used(client, monkeypatch):
    closed = row(status="used", closed_at=CREATED)
    monkeypatch.setattr(
        api_module.db, "close_item", lambda url, item_id, status: ("closed", closed)
    )
    response = client.patch("/items/1", json={"status": "used"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "used"
    assert body["closed_at"] == "2026-11-03T22:00:00+00:00"


def test_mark_unknown_item_is_404(client, monkeypatch):
    monkeypatch.setattr(
        api_module.db, "close_item", lambda url, item_id, status: ("not_found", None)
    )
    response = client.patch("/items/999", json={"status": "used"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "Item not found."}


def test_mark_closed_item_again_is_409(client, monkeypatch):
    closed = row(status="discarded", closed_at=CREATED)
    monkeypatch.setattr(
        api_module.db,
        "close_item",
        lambda url, item_id, status: ("already_closed", closed),
    )
    response = client.patch("/items/1", json={"status": "used"})
    assert response.status_code == 409
    assert response.get_json()["item"]["status"] == "discarded"


def test_status_change_rejects_bad_status(client):
    response = client.patch("/items/1", json={"status": "active"})
    assert response.status_code == 400


def test_item_id_must_be_a_number(client):
    response = client.patch("/items/abc", json={"status": "used"})
    assert response.status_code == 404


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", "/items", None),
        ("post", "/items", NEW_ITEM),
        ("patch", "/items/1", {"status": "used"}),
        ("get", "/items?status=closed", None),
        ("get", "/items/1", None),
        ("put", "/items/1", NEW_ITEM),
    ],
)
def test_database_failure_is_503_without_details(
    client, monkeypatch, method, path, body
):
    def broken(*args):
        raise psycopg.OperationalError("connection to server at 10.0.0.1 failed")

    for name in (
        "list_active_items",
        "list_closed_items",
        "get_item",
        "create_item",
        "update_item",
        "close_item",
    ):
        monkeypatch.setattr(api_module.db, name, broken)
    response = getattr(client, method)(path, json=body)
    assert response.status_code == 503
    assert response.get_json() == {"error": "Database unavailable."}
    assert b"10.0.0.1" not in response.data


# --- Closed list (history) ------------------------------------------------------


def test_list_closed_items(client, monkeypatch):
    closed = row(status="used", closed_at=CREATED)
    monkeypatch.setattr(api_module.db, "list_closed_items", lambda url: [closed])
    response = client.get("/items?status=closed")
    assert response.status_code == 200
    assert response.get_json()["items"][0]["status"] == "used"


def test_status_active_is_the_default_list(client, monkeypatch):
    monkeypatch.setattr(api_module.db, "list_active_items", lambda url: [row()])
    assert client.get("/items?status=active").get_json()["items"][0]["id"] == 1


def test_unknown_list_status_is_400(client):
    response = client.get("/items?status=eaten")
    assert response.status_code == 400
    assert response.get_json() == {
        "errors": {"status": "Must be one of: active, closed."}
    }


# --- One item -------------------------------------------------------------------


def test_get_one_item(client, monkeypatch):
    monkeypatch.setattr(api_module.db, "get_item", lambda url, item_id: row())
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.get_json()["name"] == "Greek yogurt"


def test_get_unknown_item_is_404(client, monkeypatch):
    monkeypatch.setattr(api_module.db, "get_item", lambda url, item_id: None)
    response = client.get("/items/999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Item not found."}


# --- Edit -----------------------------------------------------------------------


def test_edit_item_saves_checked_values(client, monkeypatch):
    seen = {}

    def fake_update(url, item_id, item):
        seen.update(item_id=item_id, **item)
        return "updated", row(location="cupboard")

    monkeypatch.setattr(api_module.db, "update_item", fake_update)
    response = client.put("/items/1", json={**NEW_ITEM, "location": "cupboard"})
    assert response.status_code == 200
    assert response.get_json()["location"] == "cupboard"
    assert seen["item_id"] == 1
    assert seen["label_date"] == date(2026, 11, 6)


def test_edit_rejects_bad_input_without_touching_database(client, monkeypatch):
    def must_not_run(url, item_id, item):
        raise AssertionError("database should not be called")

    monkeypatch.setattr(api_module.db, "update_item", must_not_run)
    response = client.put("/items/1", json={**NEW_ITEM, "name": ""})
    assert response.status_code == 400
    assert response.get_json() == {"errors": {"name": "Required."}}


def test_edit_unknown_item_is_404(client, monkeypatch):
    monkeypatch.setattr(
        api_module.db, "update_item", lambda url, item_id, item: ("not_found", None)
    )
    response = client.put("/items/999", json=NEW_ITEM)
    assert response.status_code == 404


def test_edit_closed_item_is_409(client, monkeypatch):
    closed = row(status="used", closed_at=CREATED)
    monkeypatch.setattr(
        api_module.db, "update_item", lambda url, item_id, item: ("closed", closed)
    )
    response = client.put("/items/1", json=NEW_ITEM)
    assert response.status_code == 409
    assert response.get_json()["error"] == "Item is closed and cannot be edited."
    assert response.get_json()["item"]["status"] == "used"
