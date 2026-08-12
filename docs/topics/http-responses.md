# HTTP Responses

Buraq provides Django-compatible HTTP response classes in `buraq.http`.

---

## Usage

```python
from buraq.http import (
    HttpResponse,
    JsonResponse,
    Http404,
    HttpResponseRedirect,
    HttpResponsePermanentRedirect,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseNotModified,
    HttpResponseGone,
    HttpResponseServerError,
    StreamingHttpResponse,
)
```

---

## HttpResponse

The base response class — like Django's `HttpResponse`.

```python
from buraq.http import HttpResponse

async def my_view(request):
    return HttpResponse("<h1>Hello</h1>")

# Custom status and content type
async def plain_text(request):
    return HttpResponse("Plain text", content_type="text/plain", status=200)

# Binary content
async def download(request):
    return HttpResponse(b"\x89PNG...", content_type="application/octet-stream")
```

### Setting headers

```python
response = HttpResponse("OK")
response["X-Custom-Header"] = "value"
response["Cache-Control"] = "no-cache"

# Check
if response.has_header("X-Custom-Header"):
    del response["X-Custom-Header"]
```

### Cookies

```python
response = HttpResponse("OK")
response.set_cookie("session_id", "abc123", httponly=True, secure=True, max_age=3600)
response.delete_cookie("old_cookie")
```

---

## JsonResponse

Returns a JSON-encoded response. Uses **orjson** (Rust-based) for serialization — significantly faster than Python's stdlib `json`.

```python
from buraq.http import JsonResponse

async def api_view(request):
    return JsonResponse({"status": "ok", "count": 42})

# Lists, primitives, etc. work by default (safe=False is the default)
async def list_view(request):
    return JsonResponse([1, 2, 3])

# Restrict to dicts only with safe=True
async def strict_view(request):
    return JsonResponse({"status": "ok"}, safe=True)

# Custom status
async def error_view(request):
    return JsonResponse({"error": "not found"}, status=404)
```

### orjson options

Pass `json_opts` to use orjson's extra serialization options:

```python
import orjson
from buraq.http import JsonResponse

# Sort keys, pretty-print
return JsonResponse(data, json_opts=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)

# Serialize numpy arrays, UUIDs, datetimes natively
return JsonResponse(data, json_opts=orjson.OPT_NON_STR_KEYS)
```

---

## StreamingHttpResponse

For large responses that should be streamed to the client without buffering — like CSV exports or large file downloads.

```python
from buraq.http import StreamingHttpResponse

async def csv_export(request):
    async def generate():
        yield b"id,name,email\n"
        async for user in User.objects.all():
            yield f"{user.id},{user.name},{user.email}\n".encode()

    response = StreamingHttpResponse(generate(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="users.csv"'
    return response
```

---

## FileResponse

Serve a file from disk with the correct `Content-Type` and `Content-Disposition`.

```python
from buraq.http import FileResponse

# Download attachment (default)
async def download_report(request):
    return FileResponse("/reports/monthly.pdf")

# Inline display (opens in browser)
async def preview_image(request, pk: int):
    doc = await Document.objects.get(id=pk)
    return FileResponse(doc.path, as_attachment=False)

# Custom download filename
async def export_csv(request):
    return FileResponse("/tmp/export.csv", filename="users.csv")
```

`as_attachment=True` (default) sets `Content-Disposition: attachment` so the browser downloads the file. Set `as_attachment=False` for inline rendering (e.g. PDFs, images).

The `Content-Type` is guessed from the filename using Python's `mimetypes` module; pass `content_type` explicitly to override:

```python
FileResponse("/data/blob", content_type="application/octet-stream")
```

---

## Http404

Raise `Http404` inside any view to return a 404 response. Buraq registers an exception handler for it automatically — no extra setup needed.

```python
from buraq.http import Http404

async def post_detail(request, pk: int):
    post = await Post.objects.get_or_none(id=pk)
    if post is None:
        raise Http404(f"Post {pk} does not exist")
    return render(request, "post.html", {"post": post})
```

!!! tip
    `get_object_or_404()` in `buraq.shortcuts` raises `Http404` automatically:
    ```python
    from buraq.shortcuts import get_object_or_404
    post = await get_object_or_404(Post, id=pk)
    ```

---

## Redirect Responses

```python
from buraq.http import HttpResponseRedirect, HttpResponsePermanentRedirect

# 302 temporary redirect
return HttpResponseRedirect("/new-url")

# 301 permanent redirect
return HttpResponsePermanentRedirect("/permanent-url")
```

!!! tip
    For simple redirects, use the `redirect()` shortcut:
    ```python
    from buraq.shortcuts import redirect
    return redirect("/dashboard")
    return redirect("/dashboard", permanent=True)
    ```

---

## Error Responses

| Class | Status | Use for |
|---|---|---|
| `HttpResponseBadRequest` | 400 | Invalid client input |
| `HttpResponseForbidden` | 403 | Permission denied |
| `HttpResponseNotFound` | 404 | Resource not found |
| `HttpResponseNotAllowed` | 405 | Wrong HTTP method |
| `HttpResponseGone` | 410 | Resource permanently removed |
| `HttpResponseServerError` | 500 | Internal error |
| `HttpResponseNotModified` | 304 | Cache hit, no body sent |

```python
from buraq.http import (
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseNotModified,
)

async def protected_view(request):
    if not request.user.is_admin:
        return HttpResponseForbidden("Admin only")

async def post_only(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

async def cached_view(request):
    etag = compute_etag()
    if request.headers.get("If-None-Match") == etag:
        return HttpResponseNotModified()
    response = HttpResponse(render_content())
    response["ETag"] = etag
    return response
```

---

## View decorators

### require_http_methods / require_GET / require_POST / require_safe

Restrict a view to specific HTTP methods — returns 405 Method Not Allowed otherwise:

```python
from buraq.decorators import require_http_methods, require_GET, require_POST, require_safe

@require_GET
async def read_only_view(request): ...

@require_POST
async def submit_view(request): ...

@require_safe          # GET and HEAD
async def idempotent_view(request): ...

@require_http_methods("GET", "POST")
async def multi_method_view(request): ...
```

### cache_control

Set `Cache-Control` response headers declaratively:

```python
from buraq.decorators import cache_control

@cache_control(max_age=3600, public=True)
async def article_detail(request, pk: int): ...

@cache_control(no_cache=True, no_store=True, must_revalidate=True)
async def private_view(request): ...
```

### never_cache

Prevent any caching of the response:

```python
from buraq.decorators import never_cache

@never_cache
async def sensitive_view(request): ...
```

Sets `Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private` plus `Expires` and `Pragma` headers.

### vary_on_headers / vary_on_cookie

Tell caches that the response varies by specific request headers:

```python
from buraq.decorators import vary_on_headers, vary_on_cookie

@vary_on_headers("Accept-Language", "Accept-Encoding")
async def localised_view(request): ...

@vary_on_cookie
async def personalised_view(request): ...
```

### condition

Return `304 Not Modified` when the client already has the current version, using ETag and/or Last-Modified callbacks you supply:

```python
from buraq.decorators import condition

def post_etag(request, pk):
    post = ... # synchronous lookup or cached value
    return f'"{post.updated_at.isoformat()}"'

def post_last_modified(request, pk):
    post = ...
    return post.updated_at   # datetime

@condition(etag_func=post_etag, last_modified_func=post_last_modified)
async def post_detail(request, pk: int):
    ...
```

Either argument may be omitted. Async callables are supported.

### conditional_page

Zero-config ETag support — computes the ETag automatically from the MD5 of the response body:

```python
from buraq.decorators import conditional_page

@conditional_page
async def article(request, pk: int):
    ...
```

Use `@condition` when you can compute the ETag cheaply before hitting the database; use `@conditional_page` when the body is always rendered anyway.

### cache_page

Cache the full response for a view for N seconds:

```python
from buraq.decorators import cache_page

@cache_page(60 * 15)   # cache for 15 minutes
async def article_list(request): ...

# Custom cache backend and key prefix
@cache_page(300, cache="secondary", key_prefix="v2")
async def search_results(request): ...
```

Only 200 OK responses are cached. Headers that must never be shared (`Set-Cookie`, `Authorization`) are stripped before storing.

---

## url_has_allowed_host_and_scheme

Guards against open redirect attacks when redirecting to a user-supplied URL.

```python
from buraq.utils.http import url_has_allowed_host_and_scheme
from buraq.conf.defaults import settings
from buraq.shortcuts import redirect
from buraq.http import HttpResponseBadRequest

async def login_view(request):
    next_url = request.query_params.get("next", "/dashboard")

    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts=set(settings.ALLOWED_HOSTS)):
        return HttpResponseBadRequest("Unsafe redirect target")

    # ... authenticate user ...
    return redirect(next_url)
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `url` | `str \| None` | The URL to validate |
| `allowed_hosts` | `str \| set[str]` | Allowed hostnames (e.g. `{"example.com"}`) |
| `require_https` | `bool` | Reject `http://` URLs (default `False`) |

Relative URLs (e.g. `/dashboard`) are always considered safe. The function rejects:

- Protocol-relative URLs (`//evil.com/steal`)
- Non-http/https schemes (`javascript:`, `data:`, etc.)
- URLs with embedded credentials (`http://user:pass@evil.com`)
- URLs with newline injection (`/path\r\nX-Header: injected`)
