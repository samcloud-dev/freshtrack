"""FreshTrack api: the only component that talks to the database."""

import logging
import os

import db
import psycopg
from flask import Flask, jsonify, request
from validation import validate_new_item, validate_status_change

log = logging.getLogger(__name__)


def database_is_reachable(database_url):
    """Return True if we can open a connection and run a trivial query."""
    if not database_url:
        log.warning("DATABASE_URL is not set")
        return False
    try:
        with db.connect(database_url) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error as exc:
        # Log the reason for operators, but never send it to the caller.
        log.warning("Database check failed: %s", exc.__class__.__name__)
        return False


def item_to_json(item):
    """Turn a database row into plain JSON values (dates as ISO text)."""
    closed_at = item["closed_at"]
    return {
        "id": item["id"],
        "name": item["name"],
        "quantity": item["quantity"],
        "location": item["location"],
        "label_date": item["label_date"].isoformat(),
        "date_type": item["date_type"],
        "status": item["status"],
        "created_at": item["created_at"].isoformat(),
        "closed_at": closed_at.isoformat() if closed_at else None,
    }


def create_app():
    app = Flask(__name__)
    app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "")

    @app.get("/health")
    def health():
        # Liveness: the process is running and can answer. No database check here,
        # otherwise a database outage would make Kubernetes restart healthy api Pods.
        return jsonify(status="ok"), 200

    @app.get("/ready")
    def ready():
        # Readiness: only accept traffic when the database is reachable.
        if database_is_reachable(app.config["DATABASE_URL"]):
            return jsonify(status="ready"), 200
        return jsonify(status="not ready"), 503

    @app.get("/items")
    def list_items():
        # Default: the active list, soonest label date first.
        # ?status=closed: used and discarded items, most recently closed first.
        which = request.args.get("status", "active")
        if which == "active":
            items = db.list_active_items(app.config["DATABASE_URL"])
        elif which == "closed":
            items = db.list_closed_items(app.config["DATABASE_URL"])
        else:
            return jsonify(errors={"status": "Must be one of: active, closed."}), 400
        return jsonify(items=[item_to_json(i) for i in items]), 200

    @app.get("/items/<int:item_id>")
    def get_item(item_id):
        item = db.get_item(app.config["DATABASE_URL"], item_id)
        if item is None:
            return jsonify(error="Item not found."), 404
        return jsonify(item_to_json(item)), 200

    @app.put("/items/<int:item_id>")
    def edit_item(item_id):
        # Fix the details of an active item (for example a wrong location).
        # Same checks as adding a new item; every field must be sent.
        item, errors = validate_new_item(request.get_json(silent=True))
        if errors:
            return jsonify(errors=errors), 400
        outcome, saved = db.update_item(app.config["DATABASE_URL"], item_id, item)
        if outcome == "not_found":
            return jsonify(error="Item not found."), 404
        if outcome == "closed":
            return jsonify(
                error="Item is closed and cannot be edited.", item=item_to_json(saved)
            ), 409
        return jsonify(item_to_json(saved)), 200

    @app.post("/items")
    def add_item():
        item, errors = validate_new_item(request.get_json(silent=True))
        if errors:
            return jsonify(errors=errors), 400
        saved = db.create_item(app.config["DATABASE_URL"], item)
        return jsonify(item_to_json(saved)), 201

    @app.patch("/items/<int:item_id>")
    def change_status(item_id):
        # The only change allowed in v1: mark an active item used or discarded.
        status, errors = validate_status_change(request.get_json(silent=True))
        if errors:
            return jsonify(errors=errors), 400
        outcome, item = db.close_item(app.config["DATABASE_URL"], item_id, status)
        if outcome == "not_found":
            return jsonify(error="Item not found."), 404
        if outcome == "already_closed":
            return jsonify(
                error="Item is already closed.", item=item_to_json(item)
            ), 409
        return jsonify(item_to_json(item)), 200

    @app.errorhandler(psycopg.Error)
    def database_error(exc):
        # The database is down or refused the request. Tell the caller only that;
        # the class name goes to the log, never connection details.
        log.error("Database error: %s", exc.__class__.__name__)
        return jsonify(error="Database unavailable."), 503

    return app
