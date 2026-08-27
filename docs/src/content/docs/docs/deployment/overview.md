---
title: "Deployment Overview"
description: "Granian is bundled with Buraq — no extra install needed."
---

## Production checklist

- [ ] `DEBUG = False`
- [ ] `SECRET_KEY` set from environment variable (not hardcoded)
- [ ] `ALLOWED_HOSTS` set to your domain(s)
- [ ] `DATABASE_URL` pointing to PostgreSQL (not SQLite)
- [ ] `CACHE_BACKEND` set to Redis
- [ ] `collectstatic` run; files served by the app, or by Granian/Nginx/a CDN with `SERVE_STATIC = False` (see [Static files](../topics/static-files.md))
- [ ] `STATICFILES_STORAGE` set to `ManifestStaticFilesStorage`, so a deploy changes the filenames and caches cannot serve the old ones
- [ ] HTTPS enabled
- [ ] Migrations applied (`buraq migrate`)

## Settings for production

```python title="config/settings.py"
import os

SECRET_KEY   = os.environ["SECRET_KEY"]
DEBUG        = False
ALLOWED_HOSTS = [os.environ.get("DOMAIN", "myapp.com")]

DATABASE_URL = os.environ["DATABASE_URL"]   # postgresql+asyncpg://...

CACHE_BACKEND   = "buraq.contrib.cache.backends.redis.RedisCacheBackend"
CACHE_REDIS_URL = os.environ["REDIS_URL"]

CORS_ORIGINS = [f"https://{os.environ.get('DOMAIN', 'myapp.com')}"]
```

## Running with Granian

Granian is bundled with Buraq — no extra install needed.

```bash
granian --interface asgi main:app \
  --workers 4 \
  --host 0.0.0.0 \
  --port 8000
```

Or via the Buraq CLI:

```bash
buraq runserver --workers 4 0.0.0.0:8000
```

## Putting a CDN in front

If the CDN fronts your own domain — Cloudflare's proxy, or any CDN set up as a
reverse proxy — there is nothing to configure here. Static files already flow
through it; give it a rule that caches `/static/*` and leave the settings alone.

If the CDN has its own hostname, point `STATIC_URL` at it:

```python title="config/settings.py"
STATIC_URL = "https://my-zone.b-cdn.net/static/"
```

Then `SERVE_STATIC` depends on how the files get there: a pull zone fetches them
from this server, so it must keep serving them; uploading to the CDN's own
storage means it must not. Getting that pair wrong is quiet — a pull zone with
`SERVE_STATIC = False` caches the 404 and serves that.

[Serving from a CDN](../topics/static-files.md#serving-from-a-cdn) has all three,
with a worked example of uploading during `collectstatic`.

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
