import app as api_module


def test_health_is_always_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_ready_when_database_is_reachable(client, monkeypatch):
    monkeypatch.setattr(api_module, "database_is_reachable", lambda url: True)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ready"}


def test_not_ready_when_database_is_unreachable(client):
    # db.invalid can never resolve, so the real connection attempt fails.
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.get_json() == {"status": "not ready"}


def test_not_ready_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = api_module.create_app().test_client().get("/ready")
    assert response.status_code == 503
