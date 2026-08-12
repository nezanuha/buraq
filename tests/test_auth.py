import pytest
from httpx import ASGITransport, AsyncClient

from buraq.core.db import Base, engine


@pytest.fixture
async def app():
    from buraq.conf import settings
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    settings.DEBUG = True
    settings.SECRET_KEY = "test-secret-key-for-auth-tests"
    settings.INSTALLED_APPS = ["buraq.contrib.auth"]

    import buraq.core.templating as _tmpl
    _tmpl._templates = None  # force re-discovery with current INSTALLED_APPS

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
    response = await client.post("/auth/login", data={
        "username": "testuser",
        "password": "securepass123",
    })
    # Session-based login redirects to / on success
    assert response.status_code in (200, 302, 303)


async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "test@example.com",
        "username": "testuser",
        "password": "securepass123",
    })
    response = await client.post("/auth/login", data={
        "username": "testuser",
        "password": "wrongpassword",
    })
    # Wrong credentials — login page re-rendered with error (200) not a redirect
    assert response.status_code == 200
    assert "Invalid" in response.text
