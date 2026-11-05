from datetime import date

import pytest
from validation import validate_new_item, validate_status_change


def good_item(**changes):
    item = {
        "name": "Greek yogurt",
        "quantity": "2 cartons",
        "location": "fridge",
        "label_date": "2026-11-06",
        "date_type": "best_before",
    }
    item.update(changes)
    return item


def test_valid_item_is_cleaned():
    item, errors = validate_new_item(good_item(name="  Greek yogurt  "))
    assert errors == {}
    assert item == {
        "name": "Greek yogurt",
        "quantity": "2 cartons",
        "location": "fridge",
        "label_date": date(2026, 11, 6),
        "date_type": "best_before",
    }


def test_past_date_is_allowed():
    # Food found after its date must still be recorded (it shows as past date).
    _, errors = validate_new_item(good_item(label_date="2020-01-01"))
    assert errors == {}


def test_unknown_fields_are_ignored():
    item, errors = validate_new_item(good_item(status="used", id=99))
    assert errors == {}
    assert "status" not in item and "id" not in item


@pytest.mark.parametrize(
    "field", ["name", "quantity", "location", "label_date", "date_type"]
)
def test_every_field_is_required(field):
    data = good_item()
    del data[field]
    _, errors = validate_new_item(data)
    assert field in errors


@pytest.mark.parametrize("value", ["", "   ", None, 5])
def test_name_must_be_real_text(value):
    _, errors = validate_new_item(good_item(name=value))
    assert errors == {"name": "Required."}


def test_name_too_long():
    _, errors = validate_new_item(good_item(name="x" * 101))
    assert errors == {"name": "At most 100 characters."}


def test_quantity_too_long():
    _, errors = validate_new_item(good_item(quantity="x" * 51))
    assert errors == {"quantity": "At most 50 characters."}


@pytest.mark.parametrize("value", ["garage", "Fridge", ""])
def test_location_must_be_known(value):
    _, errors = validate_new_item(good_item(location=value))
    assert errors == {"location": "Must be one of: fridge, freezer, cupboard."}


@pytest.mark.parametrize("value", ["expiry", "use_by", ""])
def test_date_type_must_be_known(value):
    _, errors = validate_new_item(good_item(date_type=value))
    assert errors == {"date_type": "Must be one of: best_before, expiration."}


@pytest.mark.parametrize("value", ["2026-02-30", "06/11/2026", "tomorrow"])
def test_label_date_must_be_real(value):
    _, errors = validate_new_item(good_item(label_date=value))
    assert errors == {"label_date": "Not a real date. Use YYYY-MM-DD."}


def test_label_date_must_be_text():
    _, errors = validate_new_item(good_item(label_date=20261106))
    assert errors == {"label_date": "Required, as YYYY-MM-DD."}


def test_all_errors_reported_together():
    _, errors = validate_new_item({"name": ""})
    assert set(errors) == {"name", "quantity", "location", "label_date", "date_type"}


@pytest.mark.parametrize("body", [None, [], "text"])
def test_body_must_be_an_object(body):
    assert validate_new_item(body) == (None, {"body": "Send a JSON object."})
    assert validate_status_change(body) == (None, {"body": "Send a JSON object."})


@pytest.mark.parametrize("status", ["used", "discarded"])
def test_status_change_accepts_closed_statuses(status):
    assert validate_status_change({"status": status}) == (status, {})


@pytest.mark.parametrize("status", ["active", "eaten", None])
def test_status_change_rejects_others(status):
    _, errors = validate_status_change({"status": status})
    assert errors == {"status": "Must be one of: used, discarded."}
