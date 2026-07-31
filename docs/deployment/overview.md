# Deployment Overview

## Production checklist

- [ ] `DEBUG = False`
- [ ] `SECRET_KEY` set from environment variable (not hardcoded)
- [ ] `ALLOWED_HOSTS` set to your domain(s)
- [ ] `DATABASE_URL` pointing to PostgreSQL (not SQLite)
- [ ] `CACHE_BACKEND` set to Redis
- [ ] Static files collected and served by Nginx or WhiteNoise
- [ ] HTTPS enabled
- [ ] Migrations applied (`python manage.py migrate`)

## Settings for production

```python title="config/settings.py"
import os

SECRET_KEY   = os.environ["SECRET_KEY"]
DEBUG        = False
ALLOWED_HOSTS = [os.environ.get("DOMAIN", "myapp.com")]

DATABASE_URL = os.environ["DATABASE_URL"]   # postgresql+asyncpg://...

CACHE_BACKEND   = "buraq.contrib.cache.backends.redis.RedisCacheBackend"
CACHE_REDIS_URL = os.environ["REDIS_URL"]

CORS_ALLOW_ORIGINS = [f"https://{os.environ.get('DOMAIN', 'myapp.com')}"]
```

## Running with Gunicorn + Uvicorn workers

```bash
uv add "buraq[production]"   # installs gunicorn

gunicorn config.urls:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000
```

## Nginx configuration

```nginx
server {
    listen 80;
    server_name myapp.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name myapp.com;

    ssl_certificate     /etc/letsencrypt/live/myapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/myapp.com/privkey.pem;

    location /static/ {
        alias /var/www/myapp/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```
