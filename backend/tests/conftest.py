import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    with TestClient(app) as test_client:
        yield test_client


def _register_and_login(
    client,
    username: str = "yan",
    email: str = "yan@example.com",
    password: str = "secret123",
) -> dict:
    resp = client.post(
        "/auth/signup",
        json={"username": username, "email": email, "password": password},
    )
    assert resp.status_code == 201
    login = client.post(
        "/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture()
def make_user(client):
    def _make(
        username: str = "yan",
        email: str = "yan@example.com",
        password: str = "secret123",
    ) -> dict:
        return _register_and_login(client, username, email, password)

    return _make


@pytest.fixture()
def auth_headers(make_user):
    return make_user()