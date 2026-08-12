# Testing

Buraq ships `buraq.test` — helpers for testing views, forms, and models without a running server.

## AsyncClient

Makes HTTP requests through the full ASGI stack in-process — middleware, routing, views, everything — with no server required.

```python
import pytest
from buraq.test import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_homepage(app):
    client = AsyncClient(app)
    response = await client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.text
```

### Making requests

```python
client = AsyncClient(app)

response = await client.get("/posts/")
response = await client.post("/posts/", data={"title": "Hello", "slug": "hello"})
response = await client.put("/posts/1/", data={"title": "Updated"})
response = await client.patch("/posts/1/", data={"views": 10})
response = await client.delete("/posts/1/")
response = await client.head("/posts/")
response = await client.options("/posts/")
```

### JSON requests

```python
response = await client.post("/api/posts/", json={"title": "Hello", "slug": "hello"})
data = response.json()
```

### Custom headers

```python
response = await client.get(
    "/api/me/",
    headers={"Authorization": "Bearer my-jwt-token"},
)
```

### Follow redirects

```python
response = await client.post(
    "/login/",
    data={"username": "alice", "password": "secret"},
    follow_redirects=True,
)
assert response.status_code == 200   # landed at dashboard
```

### Simulating a logged-in user

```python
user = await User.objects.get(username="alice")
client.force_login(user)

response = await client.get("/dashboard/")
assert response.status_code == 200
```

`force_login()` skips any `AUTHENTICATION_BACKENDS` that do not implement `get_user()` or `aget_user()` (e.g. permission-only backends), so it works correctly in projects with mixed backend configurations.

### Response attributes

```python
response.status_code     # int
response.text            # decoded body as str
response.content         # raw body as bytes
response.json()          # parsed JSON
response.headers         # dict of response headers
response.cookies         # SimpleCookie from Set-Cookie headers
```

## TestCase

`TestCase` integrates with Python's `unittest` and supports async setUp/tearDown:

```python
from buraq.test import TestCase


class BlogTests(TestCase):
    app = None  # set to your Buraq app instance or leave None to auto-import

    async def asyncSetUp(self):
        self.post = await Post.objects.create(
            title="Hello", slug="hello", content="World", is_published=True
        )

    async def test_list(self):
        response = await self.client.get("/posts/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hello")

    async def test_detail(self):
        response = await self.client.get("/posts/hello/")
        self.assertEqual(response.status_code, 200)

    async def asyncTearDown(self):
        await Post.objects.filter(slug="hello").delete()
```

### Assertion helpers

| Method | Description |
|---|---|
| `self.assertStatusCode(response, code)` | Assert HTTP status code |
| `self.assertContains(response, text)` | Assert text is in response body (defaults to 200) |
| `self.assertNotContains(response, text)` | Assert text is not in response body |
| `self.assertRedirects(response, url)` | Assert redirect to a specific URL |
| `self.assertJSONEqual(response, expected)` | Assert JSON body equals expected dict/list |
| `self.assertFormError(form, field, errors)` | Assert a form field has specific error(s) |
| `self.assertHTMLEqual(html1, html2)` | Compare HTML strings ignoring whitespace differences |
| `self.assertRaisesMessage(exc, message)` | Assert exception is raised with specific message text |
| `self.assertNumQueries(n)` | Assert exactly `n` SQL queries are executed in the block |
| `self.assertInHTML(needle, haystack, count=None)` | Assert HTML fragment appears in larger HTML |
| `self.assertFormsetError(formset, form_index, field, errors)` | Assert error on a specific formset form |

### assertFormError

```python
form = PostForm(data={"title": ""})
await form.is_valid()

self.assertFormError(form, "title", "This field is required.")
self.assertFormError(form, "title", ["This field is required."])  # list form
self.assertFormError(form, None, "Please fix the errors below.")  # non-field errors
```

### assertHTMLEqual

```python
self.assertHTMLEqual(
    '<p class="x">Hello</p>',
    '<p  class="x" >Hello</p>',   # extra whitespace — passes
)
```

### assertRaisesMessage

```python
with self.assertRaisesMessage(ValueError, "invalid token"):
    parse_token("bad")
```

## SimpleTestCase

For unit tests that don't need the client or database:

```python
from buraq.test import SimpleTestCase
from buraq.utils.html import escape


class EscapeTests(SimpleTestCase):
    def test_escape_html(self):
        self.assertEqual(escape("<b>Hello</b>"), "&lt;b&gt;Hello&lt;/b&gt;")
```

## TransactionTestCase

Like `TestCase` but wraps each test in a real transaction that rolls back after the test. Use when a test modifies data that must be isolated from other tests, or when the code under test calls `commit()` explicitly:

```python
from buraq.test import TransactionTestCase


class PaymentTests(TransactionTestCase):
    async def test_transfer(self):
        await transfer_funds(from_id=1, to_id=2, amount=100)
        # each test starts with a clean rolled-back state
```

!!! note
    Requires a database with savepoint support (PostgreSQL, MySQL). For most tests, plain `TestCase` is faster and sufficient.

## RequestFactory

Build `Request` objects directly without hitting the ASGI stack — useful for unit-testing a single view function in isolation:

```python
from buraq.test import RequestFactory

factory = RequestFactory()


async def test_post_detail():
    request = factory.get("/posts/hello/")
    response = await post_detail(request, slug="hello")
    assert response.status_code == 200
```

```python
async def test_create_post():
    request = factory.post("/posts/", data={"title": "Hi", "slug": "hi"})
    response = await create_post(request)
    assert response.status_code in (200, 201, 302)
```

### assertNumQueries

Assert that a block of code executes exactly `n` SQL queries:

```python
async def test_list_view(self):
    with self.assertNumQueries(1):
        response = await self.client.get("/posts/")
    self.assertEqual(response.status_code, 200)
```

### assertInHTML

Assert that an HTML fragment appears inside a larger HTML string. Whitespace differences are ignored:

```python
self.assertInHTML("<p>Hello</p>", response.text)

# Assert it appears exactly twice
self.assertInHTML('<li class="item">', response.text, count=2)
```

### assertFormsetError

Assert that a specific form in a formset has the given error:

```python
formset = BookFormSet(data={"form-TOTAL_FORMS": "2", ...})
await formset.is_valid()

self.assertFormsetError(formset, 0, "title", "This field is required.")
self.assertFormsetError(formset, 1, None, "Select a valid choice.")  # non-field errors
```

## LiveServerTestCase

`LiveServerTestCase` spins up a real ASGI server on a random port in a background thread. Use it to test code that makes real HTTP connections — e.g. Selenium or `httpx` clients:

```python
from buraq.test import LiveServerTestCase
import httpx


class LiveTests(LiveServerTestCase):
    async def test_homepage(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(self.live_server_url + "/")
        self.assertEqual(response.status_code, 200)
```

`self.live_server_url` — base URL of the test server (e.g. `http://127.0.0.1:54321`).

The server starts in `setUpClass` and shuts down in `tearDownClass` automatically.

## override_settings

Temporarily replace settings values in a test — useful for testing different configurations without changing `config/settings.py`.

### As a context manager

```python
from buraq.test import override_settings

async def test_debug_off():
    with override_settings(DEBUG=False, ALLOWED_HOSTS=["example.com"]):
        response = await client.get("/")
        # settings.DEBUG is False inside the block
    # restored to original values here
```

### As a decorator

```python
from buraq.test import override_settings

@override_settings(EMAIL_BACKEND="buraq.contrib.email.backends.memory.EmailBackend")
async def test_welcome_email(self):
    await register_user("alice@example.com")
    self.assertEqual(len(outbox), 1)
```

Works on both sync and async test methods. `setting_changed` is fired on apply and restore so middleware and caches that listen to it react correctly.

## captureOnCommitCallbacks

`on_commit()` callbacks normally only fire after a real database commit. `TestCase` wraps each test in a transaction that is always rolled back, so callbacks never fire by default.

Use `captureOnCommitCallbacks` to collect (and optionally execute) them:

```python
from buraq.test import TestCase, captureOnCommitCallbacks

class OrderTests(TestCase):
    async def test_invoice_enqueued(self):
        with captureOnCommitCallbacks(execute=True) as callbacks:
            await place_order(user_id=1, product_id=5)

        self.assertEqual(len(callbacks), 1)  # one callback was registered
```

| Parameter | Default | Description |
|---|---|---|
| `execute` | `False` | Run each callback immediately when it is registered |

---

## MessagesTestMixin

Add `assertMessages()` to any `TestCase` to verify flash messages in responses:

```python
from buraq.test import TestCase, MessagesTestMixin

class CheckoutTests(MessagesTestMixin, TestCase):
    async def test_success_message(self):
        response = await self.client.post("/checkout/", data={...})
        self.assertMessages(response, ["Order placed successfully."])

    async def test_error_message(self):
        response = await self.client.post("/checkout/", data={})
        self.assertMessages(response, ["Please correct the errors below."])
```

Pass `ordered=False` to check message presence without caring about order:

```python
self.assertMessages(response, ["Item added.", "Stock updated."], ordered=False)
```

---

## DiscoverRunner

`DiscoverRunner` is a test runner that discovers and runs tests using pytest. It is the runner used internally by the `buraq test` management command and can be used directly when you need programmatic control over test execution.

```python
from buraq.test import DiscoverRunner

runner = DiscoverRunner(verbosity=2, failfast=True)

# Run specific paths — returns failure count (0 = all passed)
failures = runner.run_tests(["tests/", "myapp/tests/test_views.py"])
```

```python
# Run from a script or CI helper
import sys
runner = DiscoverRunner()
failures = runner.run_tests()
sys.exit(failures)
```

| Parameter | Default | Description |
|---|---|---|
| `verbosity` | `1` | Output verbosity (0 = quiet, 2 = verbose) |
| `failfast` | `False` | Stop on first failure |
| `keepdb` | `False` | Reserved for future use |

`run_tests()` delegates to `pytest.main()` under the hood, so all pytest plugins and fixtures work as normal.

---

## Recommended pytest setup

Install dependencies:

```bash
uv add --dev pytest pytest-asyncio
```

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

`conftest.py`:

```python
import pytest
from config.urls import app as buraq_app


@pytest.fixture
def app():
    return buraq_app
```
