def test_health_ok_when_db_and_cache_up(client, monkeypatch):
    async def _cache_ok() -> bool:
        return True

    monkeypatch.setattr("app.routers.health._check_cache", _cache_ok)

    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "database": "ok", "cache": "ok"}


def test_health_degraded_when_db_down(client, monkeypatch):
    async def _cache_ok() -> bool:
        return True

    def _db_down() -> bool:
        return False

    monkeypatch.setattr("app.routers.health._check_cache", _cache_ok)
    monkeypatch.setattr("app.routers.health._check_db", _db_down)

    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json() == {"status": "degraded", "database": "error", "cache": "ok"}


def test_health_degraded_when_cache_down(client, monkeypatch):
    async def _cache_down() -> bool:
        return False

    monkeypatch.setattr("app.routers.health._check_cache", _cache_down)

    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json() == {"status": "degraded", "database": "ok", "cache": "error"}


def test_health_degraded_when_both_down(client, monkeypatch):
    async def _cache_down() -> bool:
        return False

    def _db_down() -> bool:
        return False

    monkeypatch.setattr("app.routers.health._check_cache", _cache_down)
    monkeypatch.setattr("app.routers.health._check_db", _db_down)

    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json() == {"status": "degraded", "database": "error", "cache": "error"}