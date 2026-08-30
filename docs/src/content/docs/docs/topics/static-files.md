---
title: "Static Files"
description: "Both forms return the same URL. When ManifestStaticFilesStorage is active, both automatically return the hashed URL (e.g. /static/css/style.abc123de.css)."
---

## Configuration

```python title="config/settings.py"
STATIC_URL  = "/static/"                     # URL prefix; a trailing slash is optional
STATIC_ROOT = str(BASE_DIR / "staticfiles")  # destination for collectstatic

# One or more source directories (in priority order)
STATICFILES_DIRS = [
    str(BASE_DIR / "static"),          # project-level static files
    str(BASE_DIR / "theme" / "static"), # shared component library, etc.
]

# Storage backend (default: local filesystem, no hashing)
STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.StaticFilesStorage"

# Finder classes — controls where collectstatic looks for files
STATICFILES_FINDERS = [
    "buraq.contrib.staticfiles.finders.FileSystemFinder",    # searches STATICFILES_DIRS
    "buraq.contrib.staticfiles.finders.AppDirectoriesFinder", # searches each app's static/
]
```

### Where source files live

`STATICFILES_DIRS` lists the project's own source directories, searched in
order; each installed app's `static/` is searched after them. Development serves
from exactly these, so a file reachable after `collectstatic` is reachable while
you are building.

```python title="config/settings.py"
STATICFILES_DIRS = [
    str(BASE_DIR / "static"),
    str(BASE_DIR / "theme" / "static"),
]
```

`STATIC_DIR` is the older single-directory form and still works — a scaffolded
project uses it, since a new project has exactly one. It is treated as one more
entry, searched after `STATICFILES_DIRS`:

```python title="config/settings.py"
STATIC_DIR = str(BASE_DIR / "static")     # equivalent to a one-entry list
```

Set one or the other; there is no reason for both.

:::caution
Neither is implied. A `static/` directory that no setting mentions is not
served and not collected — so if you remove `STATIC_DIR` from a scaffolded
project, name the directory in `STATICFILES_DIRS` instead.
:::

## In templates

Two equivalent styles — use whichever you prefer:

**Function call (Jinja2 native):**

```html+jinja
<link rel="stylesheet" href="{{ static('css/style.css') }}">
<script src="{{ static('js/app.js') }}"></script>
<img src="{{ static('images/logo.png') }}">
<img src="{{ media('uploads/photo.jpg') }}">
```

**Block tag (Django-style) — no `{% load %}` needed:**

```html+jinja
<link rel="stylesheet" href="{% static 'css/style.css' %}">
<script src="{% static 'js/app.js' %}"></script>
<img src="{% static 'images/logo.png' %}">
<img src="{% media 'uploads/photo.jpg' %}">
```

Both forms return the same URL. When `ManifestStaticFilesStorage` is active, both automatically return the hashed URL (e.g. `/static/css/style.abc123de.css`).

The `STATIC_URL` and `MEDIA_URL` prefixes are also available as template variables:

```html+jinja
<img src="{{ STATIC_URL }}images/logo.png">
<img src="{{ MEDIA_URL }}uploads/photo.jpg">
```

## Collecting for production

```bash
buraq collectstatic
```

Discovers files via all configured finders and copies them into `STATIC_ROOT`:

```
Collecting static files into /app/staticfiles ...
Done. Copied: 24, Skipped (unchanged): 8, Post-processed: 24
```

Pass `--clear` to wipe `STATIC_ROOT` before collecting:

```bash
buraq collectstatic --clear
```

## Production serving

When `DEBUG=False`, Buraq serves static files with a `Cache-Control` header, so a
browser stops asking for a file it already has, and the pre-compressed copy
`collectstatic` wrote, so nothing is compressed per request:

```
cache-control   : public, max-age=31536000, immutable
content-encoding: gzip
etag            : "fb2b605e7c9e81719c9f…"
```

How long that header lasts depends on whether filenames are hashed, because
`immutable` means *never revalidate* — a browser will not re-request the file
even when the reader hits reload:

| storage | `Cache-Control` |
|---|---|
| hashed names (`ManifestStaticFilesStorage`) | `public, max-age=31536000, immutable` |
| plain names (the default) | `public, max-age=60` |

With hashed names a changed file arrives under a different URL, so caching the
old one forever is harmless. With plain names the same URL serves new bytes after
a deploy, and a year-long `immutable` would keep your edit from anyone who had
already loaded the page.

Set `STATIC_MAX_AGE` to override the lifetime; `SERVE_STATIC = False` turns
serving off entirely when something in front handles it.

:::tip
Turning on [hashed filenames](#hashed-filenames-cache-busting) is what makes the
year-long cache safe. It is one setting, and on a site with any repeat traffic it
is the single biggest thing you can do for load time.
:::

### Pre-compression

`collectstatic` writes a `.gz` beside every compressible file, and the static
handler serves it to any client that accepts gzip:

```bash
buraq collectstatic
# Done. Copied: 1, Skipped (unchanged): 0, Post-processed: 0, compressed: 1
```

Without it, `GZipMiddleware` compresses each response as it is sent — about
2.8 ms of CPU for a 97 KB stylesheet, repeated for bytes that never change.
Measured on one worker:

| | throughput | per request |
|---|---|---|
| compressed on every request | 386 req/s | 2.59 ms |
| pre-compressed | **458 req/s** | **2.18 ms** |

Images, fonts and archives are skipped — they are already compressed — as are
files under 512 bytes, where the gzip header costs more than it saves.

`collectstatic` does this for you. To compress a file yourself — a custom
storage backend, say, or a build step that writes into `STATIC_ROOT` afterwards:

```python
from buraq.contrib.staticfiles.storage import compress_file

compress_file("staticfiles/css/site.css")   # writes site.css.gz beside it
```

It returns `True` if it wrote a `.gz`, and `False` if the file was one of the
kinds not worth compressing.

### Letting Granian serve them

Granian — Buraq's default server — serves static files itself, in Rust, without
the request entering Python at all. It costs no extra dependency, since Granian
is already one:

```python title="config/settings.py"
SERVE_STATIC = False        # the application stops mounting them
```

```bash
granian --interface asgi main:app --static-path-mount /srv/app/staticfiles
```

```
server: granian
cache-control: max-age=86400
```

`--static-path-expires` sets the lifetime and `--static-path-route` the URL
prefix, which defaults to `/static`.

#### What you give up

Granian serves the file on disk it was asked for. It does not know about the
`.gz` variants `collectstatic` wrote, so a browser gets the uncompressed file
even though it said it accepts gzip — and its `Cache-Control` is a day rather
than a year. For the stylesheet above:

| | on the wire | cache-control |
|---|---|---|
| Granian built-in | 3,040 bytes | `max-age=86400` |
| Buraq's handler | **115 bytes** | `max-age=31536000, immutable` |

Granian wins on CPU per request; Buraq's handler wins on bytes and on how often
the browser asks again. Which matters more is a question about your traffic, not
about the servers — but on a public site over real networks, sending 26× the
bytes is usually the larger cost, so **keep `SERVE_STATIC = True` unless you have
measured otherwise**.

The arrangement that gives up neither is a CDN or Nginx in front: it does its own
compression and caching, and then nothing behind it is serving static files on
the hot path at all.

### Serving from a CDN

A CDN is not something the server is pointed at — it is something the *browser*
is pointed at. There is no `--static-path-mount` for it; that flag takes a
directory on disk and refuses a hostname:

```bash
# wrong -- granian will not start
granian --interface asgi main:app --static-path-mount cdn.example.com/staticfiles
#   Error: Invalid value for '--static-path-mount':
#   Directory 'cdn.example.com/staticfiles' does not exist.
```

Which of three arrangements you are in decides what to configure — for one of
them, nothing at all:

| | `STATIC_URL` | `SERVE_STATIC` |
|---|---|---|
| [In front of your own domain](#in-front-of-your-own-domain) | `/static/` | `True` |
| [Separate hostname, CDN pulls from you](#separate-hostname-the-cdn-pulls-from-you) | the CDN | `True` |
| [Separate hostname, you upload](#separate-hostname-you-upload) | the CDN | `False` |

The mistake that is hard to spot is the middle row with `SERVE_STATIC = False`:
the CDN has nothing to pull, so it caches your 404 and serves that instead.

#### In front of your own domain

The CDN sits in front of your whole site: the same hostname, the same paths,
traffic routed through the CDN before it reaches you. Cloudflare's proxy works
this way by default, and so does a CDN configured as a reverse proxy.

Static files are already flowing through it, so there is nothing to point
anywhere:

```python title="config/settings.py"
STATIC_URL   = "/static/"    # unchanged
SERVE_STATIC = True          # unchanged
```

Caching is configured at the CDN rather than here. Give it a rule that caches
`/static/*` for a long time — the hashed filenames make that safe (see
[Hashed filenames](#hashed-filenames-cache-busting)).

If this is your setup, stop here. The two below are for a CDN on a *separate*
hostname, and doing them anyway adds a hostname you do not need.

#### Separate hostname: the CDN pulls from you

The CDN has its own host — `my-zone.b-cdn.net`, `d111.cloudfront.net`, a `cdn.`
subdomain — and templates have to point at it. That is `STATIC_URL`, and it is
the same setting for both of the arrangements below:

```python title="config/settings.py"
STATIC_URL = "https://my-zone.b-cdn.net/static/"
```

`{{ static('css/site.css') }}` now renders
`https://my-zone.b-cdn.net/static/css/site.css`. `MEDIA_URL` works the same way.

What differs is how the files get onto that host.

The CDN has no copy until somebody asks for one; on a miss it fetches from your
server and caches the result. Your server must therefore keep serving `/static/`,
so leave `SERVE_STATIC` alone:

```python title="config/settings.py"
STATIC_URL   = "https://my-zone.b-cdn.net/static/"
SERVE_STATIC = True          # the default -- the CDN pulls from here
```

Buraq mounts at the *path* of `STATIC_URL` and ignores the host, so `/static/`
stays reachable for the CDN even though templates point away from it.

Nothing to upload and nothing to invalidate: run `collectstatic`, deploy, and
change the hashed filenames (see [Hashed filenames](#hashed-filenames-cache-busting))
so a new deploy is a new URL rather than a stale cache entry.

#### Separate hostname: you upload

You copy the files to the CDN's own storage, and your server never serves them:

```bash
buraq collectstatic
# then upload staticfiles/ to the CDN's storage
```

```python title="config/settings.py"
STATIC_URL   = "https://my-zone.b-cdn.net/static/"
SERVE_STATIC = False         # nothing is served from this process
```

This is the arrangement for object storage in general — an S3 bucket behind
CloudFront is the same two settings.

To upload as part of `collectstatic` rather than as a separate step, subclass the
storage. `post_process` runs after the files are collected and hashed:

```python title="config/storage.py"
import os
from pathlib import Path
from urllib.request import Request, urlopen

from buraq.contrib.staticfiles.storage import ManifestStaticFilesStorage


class BunnyStorage(ManifestStaticFilesStorage):
    """Hash filenames as usual, then PUT everything to the storage zone."""

    zone = os.environ["BUNNY_STORAGE_ZONE"]
    key = os.environ["BUNNY_STORAGE_KEY"]
    # Regional zones have their own host -- ny.storage.bunnycdn.com, and so on.
    endpoint = os.environ.get("BUNNY_STORAGE_ENDPOINT", "https://storage.bunnycdn.com")

    def post_process(self, collected):
        yield from super().post_process(collected)
        root = Path(self.location)
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.name != self.manifest_name:
                self._upload(path.relative_to(root).as_posix(), path)
                yield path.name, path.name, True

    def _upload(self, name: str, path: Path) -> None:
        request = Request(
            f"{self.endpoint}/{self.zone}/{name}",
            data=path.read_bytes(),
            method="PUT",
            headers={"AccessKey": self.key, "Content-Type": "application/octet-stream"},
        )
        with urlopen(request) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"Bunny upload failed for {name}: {response.status}")
```

```python title="config/settings.py"
STATICFILES_STORAGE = "config.storage.BunnyStorage"
STATIC_URL          = "https://my-zone.b-cdn.net/static/"
SERVE_STATIC        = False
```

`buraq collectstatic` now collects, hashes, compresses and uploads in one step.
The `.gz` files go up with everything else, and the manifest stays local — it is
read by this process, not by the CDN.

Nothing here is Bunny-specific beyond the URL and the auth header. The same
shape works for S3, R2, Spaces or any other object store: swap `_upload`.

:::tip
Upload the `.gz` files too. `collectstatic` writes them, most CDNs will serve a
pre-compressed object when the client accepts it, and it saves the CDN doing the
same work on every miss.
:::


## Hashed filenames (cache-busting)

Switch to `ManifestStaticFilesStorage` to get content-hashed filenames:

```python title="config/settings.py"
STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.ManifestStaticFilesStorage"
```

After `buraq collectstatic`, each file is renamed to include an MD5 hash of its content:

```
css/style.css  →  css/style.abc123de.css
js/app.js      →  js/app.9f4b21cc.js
```

A manifest file (`staticfiles.json`) maps original names to hashed names. The `static()` template function and `{% static %}` tag look up the hashed URL automatically — no template changes needed:

```html+jinja
{% static 'css/style.css' %}
{# renders: /static/css/style.abc123de.css #}
```

Because the filename changes when the content changes, browsers always load the new version after a deploy — even with `Cache-Control: max-age=31536000, immutable`.

**Workflow:**

```bash
# After every deploy:
buraq collectstatic --clear
# Restart the app — it picks up the new hashed files on startup
```

## App-level static files

Each app in `INSTALLED_APPS` can ship its own static files in a `static/` subdirectory:

```
posts/
  static/
    posts/
      style.css
      logo.png
```

`AppDirectoriesFinder` (enabled by default) discovers these automatically. `buraq collectstatic` copies them alongside project-level files into `STATIC_ROOT`.

Namespace your files under the app name (e.g. `posts/style.css`) to avoid collisions between apps.

## Custom finders

Implement a finder class with `find(path)` and `list()` methods, then add it to
`STATICFILES_FINDERS`. `find` resolves one path and `list` enumerates
everything; development uses the first and `collectstatic` the second, so a
finder that implements both works in each:

```python title="myapp/finders.py"
class NodeModulesFinder:
    def find(self, path):
        full = Path("node_modules") / path
        return str(full) if full.is_file() else None

    def list(self):
        for f in Path("node_modules").rglob("*"):
            if f.is_file():
                yield str(f.relative_to("node_modules")), str(f)
```

```python title="config/settings.py"
STATICFILES_FINDERS = [
    "buraq.contrib.staticfiles.finders.FileSystemFinder",
    "buraq.contrib.staticfiles.finders.AppDirectoriesFinder",
    "myapp.finders.NodeModulesFinder",
]
```

A finder needs no directory of its own — one reading from a package, an archive
or a build tool's output works the same way, because nothing outside it assumes
files come from a filesystem tree.

## Media files

For user-uploaded files:

```python title="config/settings.py"
MEDIA_DIR = str(BASE_DIR / "media")
MEDIA_URL = "/media/"
```

Buraq auto-mounts `MEDIA_DIR` at `MEDIA_URL` when the directory exists. Use `{{ media('path') }}` or `{% media 'path' %}` in templates.

## Storage API helpers

`get_storage()` returns the singleton storage backend instance (configured by `STATICFILES_STORAGE`). `reset_storage()` clears the singleton so the next call to `get_storage()` creates a fresh instance — useful in tests that swap storage backends via `override_settings`:

```python
from buraq.contrib.staticfiles.storage import get_storage, reset_storage

storage = get_storage()
url = storage.url("css/style.css")

# In tests — after override_settings changes STATICFILES_STORAGE:
reset_storage()
storage = get_storage()   # picks up the new backend
```

## InMemoryStorage (testing)

`InMemoryStorage` stores files as bytes in a plain dict — no disk I/O, no cleanup needed. It is designed for tests that need to exercise file upload or storage logic without touching the filesystem.

```python
from buraq.contrib.staticfiles.storage import InMemoryStorage

storage = InMemoryStorage(base_url="/static/")

# Save from bytes
storage.save("logo.png", b"\x89PNG...")

# Save from a file path
storage.save("style.css", "/path/to/style.css")

# Read back
with storage.open("logo.png") as f:
    data = f.read()

storage.exists("logo.png")   # True
storage.size("logo.png")     # int
storage.url("logo.png")      # "/static/logo.png"
storage.delete("logo.png")
storage.clear()              # remove all files
```

Use globally via settings to redirect all static file operations in a test suite:

```python
# tests/conftest.py
from buraq.test import override_settings

@pytest.fixture(autouse=True)
def in_memory_static():
    with override_settings(
        STATICFILES_STORAGE="buraq.contrib.staticfiles.storage.InMemoryStorage"
    ):
        yield
```

## How it works internally

| `DEBUG` | Static backend | Media backend |
|---|---|---|
| `True` | `StaticFiles`, read from disk, no cache header | `StaticFiles` |
| `False` | `StaticFiles` + `Cache-Control: max-age=STATIC_MAX_AGE, immutable` | `StaticFiles` |
| `SERVE_STATIC = False` | nothing mounted | nothing mounted |
