import asyncio
import json
import time

import pytest

from app.core.config import settings
from app.db.models import Post, User
from app.main import _warm_feed_cache


def test_get_posts_first_call_miss(client, fake_cache):
    resp = client.get("/posts")
    assert resp.status_code == 200
    assert resp.headers["X-Cache"] == "MISS"
    assert resp.headers["Cache-Control"] == "public, max-age=30"
    assert "ETag" in resp.headers
    assert resp.json() == []


def test_get_posts_cache_hit(client, fake_cache):
    first = client.get("/posts")
    assert first.headers["X-Cache"] == "MISS"
    second = client.get("/posts")
    assert second.headers["X-Cache"] == "HIT"
    assert second.json() == first.json()


def test_get_posts_etag_304(client, fake_cache):
    first = client.get("/posts")
    etag = first.headers["ETag"]
    second = client.get("/posts", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.headers["ETag"] == etag
    assert second.headers["X-Cache"] == "HIT"


def test_etag_304_on_db_refetch_after_ttl(client, fake_cache, auth_headers):
    first = client.get("/posts")
    etag = first.headers["ETag"]
    fake_cache.ts = time.time() - settings.FEED_CACHE_TTL - 1
    resp = client.get("/posts", headers={"If-None-Match": etag})
    assert resp.status_code == 304
    assert resp.headers["ETag"] == etag


def test_cache_serves_without_db(client, fake_cache, auth_headers, db_session):
    client.get("/posts")
    session = db_session()
    session.add(Post(content="not in cache", user_id=1))
    session.commit()

    resp = client.get("/posts")
    assert resp.headers["X-Cache"] == "HIT"
    assert resp.json() == []


def test_stale_serve_on_db_failure(client, fake_cache, auth_headers, monkeypatch):
    client.get("/posts")
    fake_cache.ts = time.time() - settings.FEED_CACHE_TTL - 10

    def boom(db):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.routers.posts.load_posts", boom)
    resp = client.get("/posts")
    assert resp.status_code == 200
    assert resp.headers["X-Cache"] == "STALE"
    assert resp.headers["Warning"] == '110 - "Response is stale"'
    assert resp.json() == []


def test_stale_etag_304(client, fake_cache, auth_headers, monkeypatch):
    first = client.get("/posts")
    etag = first.headers["ETag"]
    fake_cache.ts = time.time() - settings.FEED_CACHE_TTL - 10

    def boom(db):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.routers.posts.load_posts", boom)
    resp = client.get("/posts", headers={"If-None-Match": etag})
    assert resp.status_code == 304
    assert resp.headers["X-Cache"] == "STALE"
    assert "Warning" in resp.headers


def test_total_outage_503(client, fake_cache, monkeypatch):
    def boom(db):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.routers.posts.load_posts", boom)
    resp = client.get("/posts")
    assert resp.status_code == 503
    assert resp.json() == {"detail": "Service temporarily unavailable"}


def test_post_invalidates_cache(client, fake_cache, auth_headers):
    client.get("/posts")
    assert fake_cache.data is not None

    resp = client.post("/posts", json={"content": "new post"}, headers=auth_headers)
    assert resp.status_code == 201
    assert fake_cache.data is None

    refetch = client.get("/posts")
    assert refetch.headers["X-Cache"] == "MISS"
    assert refetch.json()[0]["content"] == "new post"


def test_fresh_cache_used_even_if_db_fails(client, fake_cache, auth_headers, monkeypatch):
    client.get("/posts")

    def boom(db):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.routers.posts.load_posts", boom)
    resp = client.get("/posts")
    assert resp.headers["X-Cache"] == "HIT"
    assert resp.status_code == 200


def test_warm_feed_cache_populates_from_db(db_session, fake_cache, monkeypatch):
    session = db_session()
    session.add(User(username="warm", email="warm@example.com", hashed_password="x"))
    session.commit()
    session.add(Post(content="prewarmed post", user_id=1))
    session.commit()

    monkeypatch.setattr("app.main.SessionLocal", db_session)
    asyncio.run(_warm_feed_cache())

    assert fake_cache.data is not None
    payload = json.loads(fake_cache.data)
    assert payload[0]["content"] == "prewarmed post"
    assert payload[0]["author"]["username"] == "warm"


def test_warm_feed_cache_failure_is_silent(db_session, fake_cache, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.main.SessionLocal", boom)
    asyncio.run(_warm_feed_cache())
    assert fake_cache.data is None