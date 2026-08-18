from datetime import datetime, timedelta, timezone

from app.db.models import Post, User


def test_list_posts_empty_feed(client):
    resp = client.get("/posts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_post_requires_auth(client):
    resp = client.post("/posts", json={"content": "hello"})
    assert resp.status_code == 401


def test_create_post_invalid_token(client):
    resp = client.post(
        "/posts",
        json={"content": "hello"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


def test_create_post_success(client, auth_headers):
    resp = client.post("/posts", json={"content": "My first post!"}, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["content"] == "My first post!"
    assert body["author"]["username"] == "yan"
    assert body["author"]["id"] == 1
    assert "id" in body
    assert "created_at" in body
    assert "hashed_password" not in body


def test_create_post_trims_whitespace(client, auth_headers):
    resp = client.post("/posts", json={"content": "  spaced out  "}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["content"] == "spaced out"


def test_create_post_whitespace_only_rejected(client, auth_headers):
    resp = client.post("/posts", json={"content": "   "}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_post_empty_string_rejected(client, auth_headers):
    resp = client.post("/posts", json={"content": ""}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_post_missing_content_rejected(client, auth_headers):
    resp = client.post("/posts", json={}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_post_too_long_rejected(client, auth_headers):
    resp = client.post("/posts", json={"content": "a" * 501}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_post_500_chars_ok(client, auth_headers):
    resp = client.post("/posts", json={"content": "a" * 500}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["content"] == "a" * 500


def test_posts_newest_first(client, auth_headers, db_session):
    session = db_session()
    user = session.get(User, 1)
    base = datetime.now(timezone.utc)
    for offset, content in enumerate(["oldest", "middle", "newest"]):
        session.add(
            Post(content=content, user_id=user.id, created_at=base + timedelta(minutes=offset))
        )
    session.commit()

    resp = client.get("/posts")
    assert resp.status_code == 200
    contents = [p["content"] for p in resp.json()]
    assert contents == ["newest", "middle", "oldest"]
    assert all(p["author"]["username"] == "yan" for p in resp.json())


def test_posts_authors_from_other_users(client, auth_headers, db_session):
    session = db_session()
    session.add(
        User(username="alice", email="alice@example.com", hashed_password="x")
    )
    session.commit()
    alice = session.query(User).filter_by(username="alice").one()
    session.add(Post(content="alice post", user_id=alice.id))
    session.commit()

    client.post("/posts", json={"content": "yan post"}, headers=auth_headers)

    resp = client.get("/posts")
    authors = {p["content"]: p["author"]["username"] for p in resp.json()}
    assert authors == {"alice post": "alice", "yan post": "yan"}


def test_login_flow_with_posts_end_to_end(client, make_user):
    headers = make_user(username="bob", email="bob@example.com")
    created = client.post("/posts", json={"content": "bob says hi"}, headers=headers)
    assert created.status_code == 201
    feed = client.get("/posts")
    assert feed.json()[0]["content"] == "bob says hi"
    assert feed.json()[0]["author"]["username"] == "bob"