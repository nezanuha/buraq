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

## SimpleTestCase

For unit tests that don't need the client or database:

```python
from buraq.test import SimpleTestCase
from buraq.utils.html import escape


class EscapeTests(SimpleTestCase):
    def test_escape_html(self):
        self.assertEqual(escape("<b>Hello</b>"), "&lt;b&gt;Hello&lt;/b&gt;")
```

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
