"""The api client, with urllib replaced so no network is used."""

import io
import json
import urllib.error

import api_client
import pytest
from api_client import ApiClient, ApiUnavailable, item_path


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._raw = body if isinstance(body, bytes) else json.dumps(body).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def answer(monkeypatch, status, body, seen=None):
    """Make urlopen return this status and body (and record the request)."""

    def fake_urlopen(request, timeout):
        if seen is not None:
            seen.append(request)
        if status >= 400:
            raw = json.dumps(body).encode()
            raise urllib.error.HTTPError(
                request.full_url, status, "err", {}, io.BytesIO(raw)
            )
        return FakeResponse(status, body)

    monkeypatch.setattr(api_client.urllib.request, "urlopen", fake_urlopen)


@pytest.fixture
def client():
    return ApiClient("http://api.test/")


def test_only_http_addresses_are_allowed():
    with pytest.raises(ValueError):
        ApiClient("file:///etc/passwd")


def test_list_items(monkeypatch, client):
    seen = []
    answer(monkeypatch, 200, {"items": [{"id": 1}]}, seen)
    assert client.list_items() == [{"id": 1}]
    assert seen[0].full_url == "http://api.test/items"  # trailing slash removed
    assert seen[0].get_method() == "GET"


def test_add_item_saved(monkeypatch, client):
    seen = []
    answer(monkeypatch, 201, {"id": 7, "name": "Milk"}, seen)
    assert client.add_item({"name": "Milk"}) == ({"id": 7, "name": "Milk"}, {})
    assert json.loads(seen[0].data) == {"name": "Milk"}
    assert seen[0].get_method() == "POST"


def test_add_item_rejected(monkeypatch, client):
    answer(monkeypatch, 400, {"errors": {"name": "Required."}})
    assert client.add_item({}) == (None, {"name": "Required."})


@pytest.mark.parametrize(
    ("status", "outcome"),
    [(200, "closed"), (404, "not_found"), (409, "already_closed"), (400, "invalid")],
)
def test_close_item_outcomes(monkeypatch, client, status, outcome):
    seen = []
    answer(monkeypatch, status, {}, seen)
    assert client.close_item(5, "used") == outcome
    assert seen[0].full_url == "http://api.test/items/5"
    assert seen[0].get_method() == "PATCH"


def test_server_error_means_unavailable(monkeypatch, client):
    answer(monkeypatch, 503, {"error": "Database unavailable."})
    with pytest.raises(ApiUnavailable):
        client.list_items()


def test_connection_failure_means_unavailable(monkeypatch, client):
    def refuse(request, timeout):
        raise urllib.error.URLError(ConnectionRefusedError())

    monkeypatch.setattr(api_client.urllib.request, "urlopen", refuse)
    with pytest.raises(ApiUnavailable):
        client.list_items()


def test_timeout_means_unavailable(monkeypatch, client):
    def slow(request, timeout):
        raise TimeoutError

    monkeypatch.setattr(api_client.urllib.request, "urlopen", slow)
    with pytest.raises(ApiUnavailable):
        client.list_items()


def test_body_that_is_not_json_means_unavailable(monkeypatch, client):
    answer(monkeypatch, 200, b"<html>not json</html>")
    with pytest.raises(ApiUnavailable):
        client.list_items()


@pytest.mark.parametrize(("status", "ready"), [(200, True), (503, False)])
def test_is_ready(monkeypatch, client, status, ready):
    answer(monkeypatch, status, {})
    assert client.is_ready() is ready


def test_list_closed_items(monkeypatch, client):
    seen = []
    answer(monkeypatch, 200, {"items": [{"id": 2, "status": "used"}]}, seen)
    assert client.list_closed_items() == [{"id": 2, "status": "used"}]
    assert seen[0].full_url == "http://api.test/items?status=closed"


@pytest.mark.parametrize(("status", "result"), [(200, {"id": 3}), (404, None)])
def test_get_item(monkeypatch, client, status, result):
    answer(monkeypatch, status, {"id": 3} if status == 200 else {})
    assert client.get_item(3) == result


@pytest.mark.parametrize(
    ("status", "body", "result"),
    [
        (200, {"id": 3}, ("updated", {})),
        (400, {"errors": {"name": "Required."}}, ("invalid", {"name": "Required."})),
        (404, {}, ("not_found", {})),
        (409, {}, ("closed", {})),
    ],
)
def test_update_item_outcomes(monkeypatch, client, status, body, result):
    seen = []
    answer(monkeypatch, status, body, seen)
    assert client.update_item(3, {"name": "Milk"}) == result
    assert seen[0].full_url == "http://api.test/items/3"
    assert seen[0].get_method() == "PUT"


def test_update_item_server_error(monkeypatch, client):
    answer(monkeypatch, 503, {})
    with pytest.raises(ApiUnavailable):
        client.update_item(3, {})


@pytest.mark.parametrize("bad", ["../ready", "3/../../health", "0", "-1", "", "3.5"])
def test_item_path_refuses_anything_but_a_positive_whole_number(bad):
    with pytest.raises(ValueError):
        item_path(bad)


def test_item_path_builds_a_clean_path():
    assert item_path(3) == "/items/3"
    assert item_path("12") == "/items/12"


@pytest.mark.parametrize("method", ["get_item", "update_item", "close_item"])
def test_client_never_sends_a_traversal_path(monkeypatch, client, method):
    seen = []
    answer(monkeypatch, 200, {}, seen)
    args = {"get_item": (), "update_item": ({},), "close_item": ("used",)}[method]
    with pytest.raises(ValueError):
        getattr(client, method)("../ready", *args)
    assert seen == []  # nothing was sent to the api
