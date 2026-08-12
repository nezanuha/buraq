# Debug Error Page

When `DEBUG = True`, Buraq renders a full-page HTML traceback in the browser on any unhandled exception — no more hunting through the server console.

## What it shows

- **Exception header** — type, message, and the request method + URL
- **Traceback** — each frame with 5 lines of source context; the error line is highlighted; project frames are shown at full opacity, library frames are dimmed
- **Local variables** — collapsible per-frame table (open by default for project frames)
- **Chained exceptions** — a notice is shown when a `raise X from Y` chain is involved
- **Query string** — all URL parameters in a table
- **Request headers** — all headers except `cookie`
- **Plain-text traceback** — collapsible section for copy-pasting into a bug report

## Configuration

No configuration needed. The page is registered automatically in `Buraq._register_exception_handlers()`.

```python title="config/settings.py"
DEBUG = True   # enable the debug page (never True in production)
```

In production (`DEBUG = False`), all unhandled exceptions return a plain `500 Internal Server Error` response and the traceback is printed to the server log only.

## `render_debug_page`

The renderer is importable if you need it in a custom exception handler:

```python
from buraq.core.debug import render_debug_page
from starlette.responses import HTMLResponse

async def my_handler(request, exc):
    html = render_debug_page(request, exc)
    return HTMLResponse(content=html, status_code=500)
```

`render_debug_page(request, exc)` returns an HTML string. It is safe to call from any async context.
