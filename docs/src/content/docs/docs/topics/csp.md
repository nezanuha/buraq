---
title: "Content Security Policy"
description: "Buraq provides a ContentSecurityPolicyMiddleware that adds Content-Security-Policy headers to every response, along with per-view override decorators and a CSP…"
---

Buraq provides a `ContentSecurityPolicyMiddleware` that adds `Content-Security-Policy` headers to every response, along with per-view override decorators and a `CSP` builder utility.

---

## Setup

Add the middleware to `MIDDLEWARE`:

```python
# config/settings.py
MIDDLEWARE = [
    "buraq.middleware.security.SecurityMiddleware",
    "buraq.middleware.csp.ContentSecurityPolicyMiddleware",
    ...
]

CONTENT_SECURITY_POLICY = {
    "default-src": ["'self'"],
    "script-src":  ["'self'"],
    "style-src":   ["'self'", "'unsafe-inline'"],
    "img-src":     ["'self'", "data:"],
    "font-src":    ["'self'"],
}
```

Directive names may use hyphens (`script-src`) or underscores (`script_src`) — both are accepted.

---

## Report-only mode

To test a policy without enforcing it, set `CONTENT_SECURITY_POLICY_REPORT_ONLY`:

```python
CONTENT_SECURITY_POLICY_REPORT_ONLY = {
    "default-src": ["'self'"],
    "report-uri":  ["/csp-report/"],
}
```

This adds a `Content-Security-Policy-Report-Only` header.  Violations are reported to the `report-uri` endpoint but nothing is blocked.

---

## Nonces

A nonce lets specific inline scripts/styles bypass the CSP without using `'unsafe-inline'`.

```python
# config/settings.py
CONTENT_SECURITY_POLICY = {
    "default-src": ["'self'"],
    "script-src":  ["'self'"],
}

# Which directives receive an auto-generated per-request nonce:
CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES = ["script-src", "style-src"]
```

In templates, use `{{ request.state.csp_nonce }}`:

```html
<script nonce="{{ request.state.csp_nonce }}">
    // Inline script — allowed by the nonce
    console.log("hello");
</script>
```

A fresh nonce is generated for each request.

---

## Per-view overrides

### `csp_override`

Replace the enforced CSP for a single view:

```python
from buraq.views.decorators import csp_override

@csp_override(
    default_src=["'self'"],
    script_src=["'self'", "https://cdn.stripe.com"],
    frame_src=["https://js.stripe.com"],
)
async def checkout(request):
    ...
```

Pass `None` to disable the CSP header entirely for a view:

```python
@csp_override(None)
async def embed(request):
    # No Content-Security-Policy header.
    ...
```

### `csp_report_only_override`

Override the `Content-Security-Policy-Report-Only` header without touching the enforced policy:

```python
from buraq.views.decorators import csp_report_only_override

@csp_report_only_override(default_src=["'self'"], report_uri=["/csp-report/"])
async def experimental_view(request):
    ...
```

---

## `CSP` utility class

Build and render CSP strings programmatically:

```python
from buraq.utils.csp import CSP

policy = CSP(
    default_src=["'self'"],
    script_src=["'self'", "https://cdn.example.com"],
    img_src=["'self'", "data:"],
    upgrade_insecure_requests=True,
)

header_value = policy.as_header()
# → "default-src 'self'; script-src 'self' https://cdn.example.com; img-src 'self' data:; upgrade-insecure-requests"
```

### Nonces

```python
policy = CSP(
    default_src=["'self'"],
    script_src=["'self'", "'nonce-{nonce}'"],
    nonce=True,       # auto-generate a random nonce
)

print(policy.nonce)         # "abc123xyz..."
print(policy.as_header())   # "... script-src 'self' 'nonce-abc123xyz...'"
```

### `update()` — derive a new policy

```python
strict = CSP(default_src=["'none'"], script_src=["'self'"])
relaxed = strict.update(img_src=["'self'", "data:"])
```

---

## `csp_nonce_attr` template global

Renders `nonce="<value>"` when a nonce is set, or an empty string when nonces are not configured. Available in all Jinja2 templates automatically — no load needed.

```html
<script {{ csp_nonce_attr(request) }}>
    console.log("allowed by nonce");
</script>

<style {{ csp_nonce_attr(request) }}>
    body { margin: 0; }
</style>
```

Requires `ContentSecurityPolicyMiddleware` and `CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES` to be set.

---

## Settings reference

| Setting | Description |
|---|---|
| `CONTENT_SECURITY_POLICY` | Dict of directives for the enforced CSP header |
| `CONTENT_SECURITY_POLICY_REPORT_ONLY` | Dict of directives for the report-only header |
| `CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES` | List of directives that receive an auto-generated nonce |

### Directive value types

| Value | Result |
|---|---|
| `["'self'", "https://cdn.example.com"]` | `directive 'self' https://cdn.example.com` |
| `True` | `directive` (flag, no value) |
| `False` / `None` | Directive omitted entirely |
| `"'self'"` (bare string) | `directive 'self'` |
