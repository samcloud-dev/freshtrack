"""Page tests: the api is replaced by FakeApi (see conftest.py)."""

from datetime import date

import app as web_module
import pytest

TODAY = date(2026, 11, 11)

MILK = {
    "id": 2,
    "name": "Milk",
    "quantity": "1",
    "location": "fridge",
    "label_date": "2026-11-01",
    "date_type": "best_before",
    "status": "active",
}
JUICE = {**MILK, "id": 1, "name": "Juice", "label_date": "2026-11-13"}
PEAS = {
    **MILK,
    "id": 3,
    "name": "Frozen peas",
    "location": "freezer",
    "label_date": "2027-03-01",
    "date_type": "expiration",
}

GOOD_FORM = {
    "name": "Greek yogurt",
    "quantity": "2",
    "location": "fridge",
    "label_date": "2026-11-18",
    "date_type": "best_before",
}


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(web_module, "today", lambda timezone: TODAY)


# --- Page 1 ---------------------------------------------------------------


def test_home_groups_items_and_uses_date_type_words(client, fake_api):
    fake_api.items = [MILK, JUICE, PEAS]
    page = client.get("/").get_data(as_text=True)
    assert 'Date passed <span class="count">(1)</span>' in page
    assert 'Next 3 days <span class="count">(1)</span>' in page
    assert 'Later <span class="count">(1)</span>' in page
    assert "Best before 1 Nov · 10 days ago" in page
    assert "Best before 13 Nov · in 2 days" in page
    assert "Expiration date 1 Mar 2027" in page


def test_home_filters_by_location(client, fake_api):
    fake_api.items = [MILK, PEAS]
    page = client.get("/?location=freezer").get_data(as_text=True)
    assert "Frozen peas" in page
    assert "Milk" not in page


def test_home_ignores_an_unknown_location(client, fake_api):
    fake_api.items = [MILK, PEAS]
    page = client.get("/?location=garage").get_data(as_text=True)
    assert "Frozen peas" in page and "Milk" in page


def test_home_empty_list(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.get_data(as_text=True).count("Nothing here.") == 3


def test_every_page_says_it_does_not_judge_safety(client):
    for path in ("/", "/add"):
        assert "does not judge whether food is safe" in client.get(path).get_data(
            as_text=True
        )


def test_item_names_are_escaped(client, fake_api):
    fake_api.items = [{**MILK, "name": "<script>alert(1)</script>"}]
    page = client.get("/").get_data(as_text=True)
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


# --- Page 2 ---------------------------------------------------------------


def test_add_form_has_sensible_defaults(client):
    page = client.get("/add").get_data(as_text=True)
    assert 'value="fridge" checked' in page
    assert 'value="best_before" checked' in page
    assert 'name="quantity" type="text" maxlength="50" value="1"' in page


def test_add_saves_and_returns_home_with_a_message(client, fake_api, csrf):
    response = client.post("/add", data={**GOOD_FORM, "csrf_token": csrf})
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert fake_api.added == [GOOD_FORM]
    assert "Greek yogurt added." in client.get("/").get_data(as_text=True)


def test_save_and_add_another_keeps_location_and_date_type(client, csrf):
    form = {**GOOD_FORM, "location": "freezer", "date_type": "expiration"}
    response = client.post("/add", data={**form, "csrf_token": csrf, "again": "1"})
    assert response.headers["Location"] == "/add?location=freezer&date_type=expiration"


def test_add_errors_stay_on_the_page_with_plain_help(client, fake_api, csrf):
    fake_api.add_errors = {"location": "Must be one of: fridge, freezer, cupboard."}
    form = {**GOOD_FORM, "location": ""}
    response = client.post("/add", data={**form, "csrf_token": csrf})
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Choose where it is stored." in page
    assert 'value="Greek yogurt"' in page  # what was typed is kept


def test_add_trims_spaces(client, fake_api, csrf):
    client.post("/add", data={**GOOD_FORM, "name": "  Milk  ", "csrf_token": csrf})
    assert fake_api.added[0]["name"] == "Milk"


# --- Used / Discarded -----------------------------------------------------


def test_mark_used_calls_the_api_and_shows_a_message(client, fake_api, csrf):
    response = client.post(
        "/items/2/status", data={"status": "used", "name": "Milk", "csrf_token": csrf}
    )
    assert response.status_code == 302
    assert fake_api.closed == [(2, "used")]
    assert "Milk marked as used." in client.get("/").get_data(as_text=True)


def test_mark_keeps_the_location_filter(client, csrf):
    data = {"status": "discarded", "location": "freezer", "csrf_token": csrf}
    response = client.post("/items/3/status", data=data)
    assert response.headers["Location"] == "/?location=freezer"


def test_mark_an_item_that_was_already_closed(client, fake_api, csrf):
    fake_api.close_outcome = "already_closed"
    client.post("/items/2/status", data={"status": "used", "csrf_token": csrf})
    assert "That item was already updated." in client.get("/").get_data(as_text=True)


def test_mark_with_an_unknown_status_is_refused(client, fake_api, csrf):
    response = client.post(
        "/items/2/status", data={"status": "eaten", "csrf_token": csrf}
    )
    assert response.status_code == 400
    assert fake_api.closed == []


# --- Form protection --------------------------------------------------------


@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_forms_without_the_right_token_are_refused(client, fake_api, csrf, token):
    data = dict(GOOD_FORM)
    if token:
        data["csrf_token"] = token
    assert client.post("/add", data=data).status_code == 400
    assert fake_api.added == []


def test_pages_include_a_form_token(client, fake_api):
    fake_api.items = [MILK]
    assert 'name="csrf_token"' in client.get("/").get_data(as_text=True)
    assert 'name="csrf_token"' in client.get("/add").get_data(as_text=True)


# --- Api down, probes, headers ---------------------------------------------


def test_api_down_shows_a_friendly_page(client, fake_api):
    fake_api.down = True
    response = client.get("/")
    assert response.status_code == 503
    assert "can't reach its list right now" in response.get_data(as_text=True)


def test_health_never_asks_the_api(client, fake_api):
    fake_api.down = True
    fake_api.ready = False
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(("ready", "code"), [(True, 200), (False, 503)])
def test_ready_follows_the_api(client, fake_api, ready, code):
    fake_api.ready = ready
    assert client.get("/ready").status_code == code


def test_security_headers(client):
    headers = client.get("/health").headers
    assert "script-src" not in headers["Content-Security-Policy"]
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"


# --- Startup settings -------------------------------------------------------


@pytest.mark.parametrize("missing", ["SECRET_KEY", "API_URL"])
def test_missing_setting_stops_startup(monkeypatch, missing):
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("API_URL", "http://api.invalid")
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        web_module.create_app()


def test_wrong_time_zone_stops_startup(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("API_URL", "http://api.invalid")
    monkeypatch.setenv("TIMEZONE", "Mars/Olympus")
    with pytest.raises(Exception, match="Mars/Olympus"):
        web_module.create_app()


# --- Edit -----------------------------------------------------------------------

TOMATOES = {
    **MILK,
    "id": 3,
    "name": "Canned tomatoes",
    "location": "freezer",
    "label_date": "2027-02-12",
    "date_type": "expiration",
}


def test_home_cards_have_an_edit_link(client, fake_api):
    fake_api.items = [TOMATOES]
    assert 'href="/items/3/edit"' in client.get("/").get_data(as_text=True)


def test_edit_form_is_filled_in(client, fake_api):
    fake_api.items = [TOMATOES]
    page = client.get("/items/3/edit").get_data(as_text=True)
    assert "Edit food" in page
    assert 'value="Canned tomatoes"' in page
    assert 'value="freezer" checked' in page
    assert 'value="expiration" checked' in page
    assert 'value="2027-02-12"' in page
    assert 'action="/items/3/edit"' in page
    assert "Save and add another" not in page


def test_edit_saves_and_returns_home(client, fake_api, csrf):
    fake_api.items = [TOMATOES]
    form = {**GOOD_FORM, "name": "Canned tomatoes", "location": "cupboard"}
    response = client.post("/items/3/edit", data={**form, "csrf_token": csrf})
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert fake_api.updated == [(3, form)]
    assert "Canned tomatoes updated." in client.get("/").get_data(as_text=True)


def test_edit_errors_stay_on_the_page(client, fake_api, csrf):
    fake_api.items = [TOMATOES]
    fake_api.update_outcome = ("invalid", {"name": "Required."})
    form = {**GOOD_FORM, "name": ""}
    response = client.post("/items/3/edit", data={**form, "csrf_token": csrf})
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Enter a name, up to 100 characters." in page
    assert 'action="/items/3/edit"' in page


def test_edit_a_closed_item_is_refused(client, fake_api):
    fake_api.closed_items = [{**MILK, "status": "used"}]
    response = client.get("/items/2/edit")
    assert response.status_code == 302
    assert "Milk is already used, so it cannot be edited." in client.get("/").get_data(
        as_text=True
    )


def test_edit_an_unknown_item(client):
    response = client.get("/items/999/edit")
    assert response.status_code == 302
    assert "That item no longer exists." in client.get("/").get_data(as_text=True)


def test_item_closed_while_editing(client, fake_api, csrf):
    # Someone pressed Used on another phone before Save was pressed.
    fake_api.closed_items = [{**TOMATOES, "status": "used"}]
    fake_api.update_outcome = ("closed", {})
    response = client.post("/items/3/edit", data={**GOOD_FORM, "csrf_token": csrf})
    assert response.status_code == 302
    assert "already used, so it cannot be edited" in client.get("/").get_data(
        as_text=True
    )


def test_edit_needs_the_form_token(client, fake_api):
    fake_api.items = [TOMATOES]
    assert client.post("/items/3/edit", data=GOOD_FORM).status_code == 400
    assert fake_api.updated == []


# --- History --------------------------------------------------------------------


def closed(name, status, closed_at):
    return {**MILK, "name": name, "status": status, "closed_at": closed_at}


def test_history_lists_closed_items_with_toronto_dates(client, fake_api):
    fake_api.closed_items = [
        # 02:30 UTC on 11 Nov is still 10 Nov in Toronto.
        closed("Bread", "discarded", "2026-11-11T02:30:00+00:00"),
        closed("Milk", "used", "2026-11-09T21:10:19+00:00"),
    ]
    page = client.get("/history").get_data(as_text=True)
    assert "Bread" in page and "Discarded 10 Nov" in page
    assert "Milk" in page and "Used 9 Nov" in page


def test_history_summary_counts_the_last_7_days(client, fake_api):
    fake_api.closed_items = [
        closed("Milk", "used", "2026-11-10T15:00:00+00:00"),
        closed("Juice", "used", "2026-11-08T15:00:00+00:00"),
        closed("Bread", "discarded", "2026-11-09T15:00:00+00:00"),
        closed("Old cheese", "used", "2026-10-20T15:00:00+00:00"),  # too old
    ]
    page = client.get("/history").get_data(as_text=True)
    assert "<strong>2 used</strong>" in page
    assert "<strong>1 discarded</strong>" in page


def test_history_empty(client):
    page = client.get("/history").get_data(as_text=True)
    assert "Nothing used or discarded yet." in page


def test_home_links_to_history(client):
    assert 'href="/history"' in client.get("/").get_data(as_text=True)
