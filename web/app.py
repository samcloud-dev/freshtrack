"""FreshTrack web: the pages people see.

It never touches the database. Every read and write goes through the api.
"""

import hmac
import logging
import os
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from api_client import ApiClient, ApiUnavailable
from dates import format_day, group_items
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

log = logging.getLogger(__name__)

LOCATIONS = ("fridge", "freezer", "cupboard")
DATE_TYPES = ("best_before", "expiration")
CLOSED_STATUSES = ("used", "discarded")
ITEM_FIELDS = ("name", "quantity", "location", "label_date", "date_type")

# Plain-language messages for each field. The api decides what is wrong;
# the page says how to fix it.
FIELD_HELP = {
    "name": "Enter a name, up to 100 characters.",
    "quantity": "Enter a quantity, up to 50 characters (for example 1, 2 cartons, 500 g).",
    "location": "Choose where it is stored.",
    "label_date": "Choose the date printed on the label.",
    "date_type": "Choose what the label says.",
}


def today(timezone):
    """Today's date in the household's time zone (not the server's)."""
    return datetime.now(ZoneInfo(timezone)).date()


def required_setting(name):
    value = os.environ.get(name, "")
    if not value:
        # Fail at startup with a clear message, instead of failing on the first page.
        raise RuntimeError(f"{name} is not set")
    return value


def create_app():
    app = Flask(__name__)
    # Signs the session cookie (used for form tokens and messages). From a Secret.
    app.config["SECRET_KEY"] = required_setting("SECRET_KEY")
    app.config["API"] = ApiClient(required_setting("API_URL"))
    app.config["TIMEZONE"] = os.environ.get("TIMEZONE", "America/Toronto")
    ZoneInfo(app.config["TIMEZONE"])  # A wrong name fails here, at startup.

    # The cookie is never readable by scripts, and only sent over HTTPS
    # (browsers also allow it on http://localhost for local testing).
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("COOKIE_SECURE", "true") == "true"
    )

    def api():
        return app.config["API"]

    # --- Form protection (CSRF) ---------------------------------------------
    # Every form carries a random token that only our own pages know. A form
    # posted from another website does not have it, so it is refused.
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def check_csrf():
        if request.method != "POST":
            return
        sent = request.form.get("csrf_token", "").encode("utf-8")
        expected = session.get("csrf", "").encode("utf-8")
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400)

    # --- Browser safety headers ----------------------------------------------
    @app.after_request
    def security_headers(response):
        # Only our own styles; no scripts at all; forms post only to us; no framing.
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'self'; img-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    # --- Probes --------------------------------------------------------------
    @app.get("/health")
    def health():
        # Alive = the process answers. Never checks the api.
        return jsonify(status="ok"), 200

    @app.get("/ready")
    def ready():
        # Ready = the api answers its own /ready (so the database is reachable too).
        if api().is_ready():
            return jsonify(status="ready"), 200
        return jsonify(status="not ready"), 503

    # --- Page 1: what's at home ----------------------------------------------
    @app.get("/")
    def index():
        location = request.args.get("location")
        if location not in LOCATIONS:
            location = None
        items = api().list_items()
        if location:
            items = [i for i in items if i["location"] == location]
        groups = group_items(items, today(app.config["TIMEZONE"]))
        return render_template(
            "index.html", groups=groups, location=location, locations=LOCATIONS
        )

    # --- Page 2: add food ----------------------------------------------------
    @app.get("/add")
    def add_form():
        # Remember location and date type after "Save and add another".
        form = {
            "quantity": "1",
            "location": request.args.get("location", "fridge"),
            "date_type": request.args.get("date_type", "best_before"),
        }
        return render_add(form, {})

    def render_add(form, errors, status=200):
        return render_template(
            "item_form.html",
            mode="add",
            action=url_for("add_submit"),
            form=form,
            errors=errors,
        ), status

    def submitted_form():
        return {field: request.form.get(field, "").strip() for field in ITEM_FIELDS}

    def friendly(errors):
        return {field: FIELD_HELP.get(field, text) for field, text in errors.items()}

    @app.post("/add")
    def add_submit():
        form = submitted_form()
        item, errors = api().add_item(form)
        if errors:
            return render_add(form, friendly(errors), 400)
        flash(f"{item['name']} added.")
        if request.form.get("again"):
            return redirect(
                url_for(
                    "add_form", location=form["location"], date_type=form["date_type"]
                )
            )
        return redirect(url_for("index"))

    # --- Used / Discarded buttons --------------------------------------------
    @app.post("/items/<int:item_id>/status")
    def change_status(item_id):
        status = request.form.get("status", "")
        name = request.form.get("name", "Item")[:100]
        location = request.form.get("location")
        if status not in CLOSED_STATUSES:
            abort(400)
        outcome = api().close_item(item_id, status)
        if outcome == "closed":
            flash(f"{name} marked as {status}.")
        elif outcome in ("not_found", "already_closed"):
            flash("That item was already updated.")
        else:
            abort(400)
        if location in LOCATIONS:
            return redirect(url_for("index", location=location))
        return redirect(url_for("index"))

    # --- Edit an item (fix a mistake) -----------------------------------------
    def render_edit(item_id, form, errors, status=200):
        return render_template(
            "item_form.html",
            mode="edit",
            action=url_for("edit_submit", item_id=item_id),
            form=form,
            errors=errors,
        ), status

    def cannot_edit(item):
        """Send the person back to the list when the item is gone or closed."""
        if item is None:
            flash("That item no longer exists.")
        else:
            flash(
                f"{item['name']} is already {item['status']}, so it cannot be edited."
            )
        return redirect(url_for("index"))

    @app.get("/items/<int:item_id>/edit")
    def edit_form(item_id):
        item = api().get_item(item_id)
        if item is None or item["status"] != "active":
            return cannot_edit(item)
        form = {field: item[field] for field in ITEM_FIELDS}
        return render_edit(item_id, form, {})

    @app.post("/items/<int:item_id>/edit")
    def edit_submit(item_id):
        form = submitted_form()
        outcome, errors = api().update_item(item_id, form)
        if outcome == "invalid":
            return render_edit(item_id, form, friendly(errors), 400)
        if outcome == "updated":
            flash(f"{form['name']} updated.")
            return redirect(url_for("index"))
        # Closed or deleted between opening the form and saving it.
        return cannot_edit(api().get_item(item_id))

    # --- Page 3: used and discarded (the trial record) -------------------------
    @app.get("/history")
    def history():
        timezone = ZoneInfo(app.config["TIMEZONE"])
        now = today(app.config["TIMEZONE"])
        rows = []
        for item in api().list_closed_items():
            closed_on = datetime.fromisoformat(item["closed_at"]).astimezone(timezone)
            closed_day = closed_on.date()
            rows.append(
                {
                    **item,
                    "closed_on": closed_day,
                    "closed_text": format_day(closed_day, now),
                }
            )
        recent = [r for r in rows if (now - r["closed_on"]).days < 7]
        summary = {
            "used": sum(r["status"] == "used" for r in recent),
            "discarded": sum(r["status"] == "discarded" for r in recent),
        }
        return render_template("history.html", rows=rows, summary=summary, today=now)

    # --- When the api is down ------------------------------------------------
    @app.errorhandler(ApiUnavailable)
    def api_unavailable(exc):
        return render_template("error.html"), 503

    return app
