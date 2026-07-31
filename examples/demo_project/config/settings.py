from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-secret-key-change-in-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "buraq.contrib.auth",  # built-in auth
    "users",                # custom app
]

DATABASE_URL = "sqlite+aiosqlite:///./demo.sqlite3"

TEMPLATES_DIR = str(BASE_DIR / "templates")
STATIC_DIR = str(BASE_DIR / "static")

CORS_ORIGINS = ["http://localhost:3000"]
RATE_LIMIT = "200/minute"
