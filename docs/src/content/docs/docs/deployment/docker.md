---
title: "Docker"
description: "Containerise a Buraq app with Docker — a slim Python 3.12 Dockerfile running Granian, and a docker-compose stack with PostgreSQL 16."
---

## Dockerfile

```dockerfile title="Dockerfile"
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev --frozen

# Copy application code
COPY . .

# Collect static files
RUN uv run buraq collectstatic --no-input

EXPOSE 8000

CMD ["uv", "run", "granian", "--interface", "asgi", "main:app", \
     "--workers", "4", \
     "--host", "0.0.0.0", \
     "--port", "8000"]
```

## docker-compose.yml

```yaml title="docker-compose.yml"
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgresql+asyncpg://buraq:buraq@db:5432/buraq_db
      - REDIS_URL=redis://redis:6379/0
      - DEBUG=False
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    command: >
      sh -c "uv run buraq migrate &&
             uv run granian --interface asgi main:app
               --workers 4 --host 0.0.0.0 --port 8000"

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: buraq
      POSTGRES_PASSWORD: buraq
      POSTGRES_DB: buraq_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U buraq"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## Running

```bash
# Development
docker compose up

# Production (detached)
docker compose up -d

# View logs
docker compose logs -f web

# Run migrations
docker compose exec web buraq migrate

# Create superuser
docker compose exec web buraq createsuperuser
```
