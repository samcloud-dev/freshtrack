"""Checks on what the caller sends, before anything reaches the database.

Each function returns (clean_value, errors). errors is a dict of
field name -> plain-language message; an empty dict means the input is valid.
The database repeats the same rules (schema.sql), so bad data cannot slip in another way.
"""

from datetime import date

LOCATIONS = ("fridge", "freezer", "cupboard")
DATE_TYPES = ("best_before", "expiration")
CLOSED_STATUSES = ("used", "discarded")

NAME_MAX = 100
QUANTITY_MAX = 50


def _text(data, field, max_length, errors):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        errors[field] = "Required."
        return None
    value = value.strip()
    if len(value) > max_length:
        errors[field] = f"At most {max_length} characters."
        return None
    return value


def _choice(data, field, allowed, errors):
    value = data.get(field)
    if value not in allowed:
        errors[field] = "Must be one of: " + ", ".join(allowed) + "."
        return None
    return value


def _label_date(data, errors):
    value = data.get("label_date")
    if not isinstance(value, str):
        errors["label_date"] = "Required, as YYYY-MM-DD."
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        errors["label_date"] = "Not a real date. Use YYYY-MM-DD."
        return None


def validate_new_item(data):
    """Check a new item. Unknown fields are ignored."""
    if not isinstance(data, dict):
        return None, {"body": "Send a JSON object."}

    errors = {}
    item = {
        "name": _text(data, "name", NAME_MAX, errors),
        "quantity": _text(data, "quantity", QUANTITY_MAX, errors),
        "location": _choice(data, "location", LOCATIONS, errors),
        "label_date": _label_date(data, errors),
        "date_type": _choice(data, "date_type", DATE_TYPES, errors),
    }
    if errors:
        return None, errors
    return item, {}


def validate_status_change(data):
    """Check a request to mark an item used or discarded."""
    if not isinstance(data, dict):
        return None, {"body": "Send a JSON object."}
    errors = {}
    status = _choice(data, "status", CLOSED_STATUSES, errors)
    if errors:
        return None, errors
    return status, {}
