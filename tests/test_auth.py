import pytest
from httpx import AsyncClient, ASGITransport
from buraq import Buraq
from buraq.core.db import Base, engine


@pytest.fixture
async def app():
    from buraq.conf import settings
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    settings.DEBUG = True
    settings.INSTALLED_APPS = ["buraq.contrib.auth"]

    from buraq.core.application import Buraq as BuraqApp
    _app = BuraqApp()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield _app

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_register(client):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "securepass123",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"


async def test_login(client):
    await client.post("/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "securepass123",
    })
    response = await client.post("/auth/token", json={
        "username": "testuser",
        "password": "securepass123",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "securepass123",
    })
    response = await client.post("/auth/token", json={
        "username": "testuser",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
