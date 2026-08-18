def test_health_ok_when_db_and_cache_up(client, monkeypatch):
    async def _cache_ok() -> bool:
        return True

    monkeypatch.setattr("app.routers.health._check_cache", _cache_ok)

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"db": True, "cache": True}


def test_health_degraded_when_db_down(client, monkeypatch):
    async def _cache_ok() -> bool:
        return True

    def _db_down() -> bool:
        return False

    monkeypatch.setattr("app.routers.health._check_cache", _cache_ok)
    monkeypatch.setattr("app.routers.health._check_db", _db_down)

    resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"] == {"db": False, "cache": True}


def test_health_ok_with_cache_down(client, monkeypatch):
    async def _cache_down() -> bool:
        return False

    monkeypatch.setattr("app.routers.health._check_cache", _cache_down)

    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["checks"]["cache"] is False