"""The only file in web that talks to the api.

Uses Python's built-in urllib, so web needs no extra HTTP package.
"""

import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

# Give up on a slow api instead of leaving the page hanging.
TIMEOUT_SECONDS = 5


class ApiUnavailable(Exception):
    """The api could not be reached, or it answered with a server error."""


class ApiClient:
    def __init__(self, base_url):
        # Only plain web addresses: never file:// or other schemes.
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("API_URL must start with http:// or https://")
        self.base_url = base_url.rstrip("/")

    def _call(self, method, path, body=None):
        """Send one request to the api. Returns (status code, JSON body)."""
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            # The scheme is checked in __init__, so this only opens http(s) URLs.
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as exc:
            # 4xx/5xx still carry a JSON body from the api.
            status, raw = exc.code, exc.read()
        except OSError as exc:
            # Connection refused, DNS failure, timeout. The class name only, never the URL.
            log.error("api unreachable: %s", exc.__class__.__name__)
            raise ApiUnavailable from exc

        if status >= 500:
            log.error("api answered %s for %s %s", status, method, path)
            raise ApiUnavailable
        try:
            return status, json.loads(raw)
        except ValueError as exc:
            log.error("api sent a body that is not JSON (%s %s)", method, path)
            raise ApiUnavailable from exc

    def is_ready(self):
        """True if the api says it is ready (it can reach the database)."""
        try:
            status, _ = self._call("GET", "/ready")
        except ApiUnavailable:
            return False
        return status == 200

    def list_items(self):
        """Active items, soonest label date first (the api sorts them)."""
        status, body = self._call("GET", "/items")
        if status != 200:
            raise ApiUnavailable
        return body["items"]

    def list_closed_items(self):
        """Used and discarded items, most recently closed first."""
        status, body = self._call("GET", "/items?status=closed")
        if status != 200:
            raise ApiUnavailable
        return body["items"]

    def get_item(self, item_id):
        """One item (active or closed), or None if it does not exist."""
        status, body = self._call("GET", f"/items/{item_id}")
        if status == 200:
            return body
        if status == 404:
            return None
        raise ApiUnavailable

    def update_item(self, item_id, fields):
        """Save new details for an active item.

        Returns (outcome, errors): ("updated", {}), ("invalid", errors),
        ("not_found", {}) or ("closed", {}).
        """
        status, body = self._call("PUT", f"/items/{item_id}", fields)
        if status == 200:
            return "updated", {}
        if status == 400:
            return "invalid", body.get("errors", {})
        if status == 404:
            return "not_found", {}
        if status == 409:
            return "closed", {}
        raise ApiUnavailable

    def add_item(self, fields):
        """Returns (item, {}) when saved, or (None, errors) when the api rejects it."""
        status, body = self._call("POST", "/items", fields)
        if status == 201:
            return body, {}
        if status == 400:
            return None, body.get("errors", {})
        raise ApiUnavailable

    def close_item(self, item_id, status_value):
        """Mark an item used or discarded.

        Returns "closed", "not_found", "already_closed" or "invalid".
        """
        status, _ = self._call("PATCH", f"/items/{item_id}", {"status": status_value})
        outcomes = {
            200: "closed",
            404: "not_found",
            409: "already_closed",
            400: "invalid",
        }
        if status in outcomes:
            return outcomes[status]
        raise ApiUnavailable
