---
title: "Schemas"
description: "Pydantic schemas describe the JSON an endpoint accepts and returns. buraq startapp writes a schemas.py; this is what it is for."
---

`buraq startapp` writes a `schemas.py`. It is empty of meaning until you serve
JSON, and it does nothing at all for a view that renders a template — so if
your app only has HTML pages, you can delete the file and never think about it
again.

What it is for is the other kind of endpoint: one that takes JSON in and sends
JSON out.

## What a schema does

A model describes a row in the database. A schema describes a message on the
wire, and the two are deliberately not the same shape:

```python title="posts/models.py"
class Post(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
```

```python title="posts/schemas.py"
from pydantic import BaseModel


class PostRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    name: str
```

Two classes because the directions differ.

**`PostCreate` is what you accept.** It lists `name` and nothing else, so a
request that sends `id` or `created_at` cannot set them — those belong to the
database, not the caller. A request missing `name`, or sending a number where a
string belongs, is rejected with a 422 describing the problem before your view
runs.

**`PostRead` is what you return.** It lists `id` and `name`, so `created_at`
never leaves the server even though the model has it. Adding a field to the
model does not silently start publishing it; you decide, per schema, by adding
it here.

`model_config = {"from_attributes": True}` is what lets `PostRead` be built
from a model instance rather than a dictionary. Without it Pydantic expects
`{"id": 1, "name": "..."}` and a `Post` object raises. It is on the schema you
send *out*, because that is the one handed an object; `PostCreate` is built from
the request body, which is already a dictionary.

## Using them

```python title="posts/api.py"
from buraq.views.decorators.csrf import csrf_exempt

from posts.models import Post
from posts.schemas import PostCreate, PostRead


async def list_posts(request) -> list[PostRead]:
    return await Post.objects.all()


@csrf_exempt
async def create_post(request, payload: PostCreate) -> PostRead:
    return await Post.objects.create(name=payload.name)
```

```python title="config/urls.py"
from buraq.urls import get, post

urlpatterns = [
    get("/api/posts", api.list_posts, name="api_list"),
    post("/api/posts", api.create_post, name="api_create"),
]
```

```
POST /api/posts   {"name": "Hello"}    →  200  {"id": 1, "name": "Hello"}
GET  /api/posts                        →  200  [{"id": 1, "name": "Hello"}]
```

`created_at` is on the model and not in either response. That is the schema
doing its job.

:::caution[A JSON endpoint needs `@csrf_exempt`]
CSRF protection is on by default and expects a token in the form body, which a
JSON client has no way to send. Without the decorator the `POST` above is
refused with `403 CSRF verification failed`. Only exempt endpoints that
authenticate some other way — a bearer token, an API key — never a view that
relies on the session cookie.
:::

## Where they show up

Passing the schema as `response_model` puts it in the generated API
documentation at `/api/docs`, with the fields, their types and an example:

```python
get("/api/posts", api.list_posts,
    name="api_list",
    response_model=list[PostRead],
    tags=["posts"],
    summary="List all posts",
)
```

Anything else FastAPI's route decorator accepts can go there too — see
[Extra route options](urls.md#extra-route-options).

## When not to bother

- The view renders a template. Templates read the model directly; a schema adds
  nothing.
- The endpoint returns something that is not a model — a count, a status. Return
  a dict.
- You are the only caller and the shape is settled. A schema earns its place
  when something outside your code depends on the shape staying still.
