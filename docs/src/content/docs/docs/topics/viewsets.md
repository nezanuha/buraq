---
title: "Viewsets & Routers"
description: "One class per JSON resource instead of five views, five routes and five names."
---

A JSON resource is nearly always the same five actions over the same model.
Written out, that is five view functions, five `path()` calls, and five route
names kept in step with both — repeated for every model in the project.

A viewset states the model once and a router turns it into the routes.

```python title="posts/api.py"
from buraq.views.viewsets import ModelViewSet

from posts.models import Post
from posts.schemas import PostCreate, PostRead


class PostViewSet(ModelViewSet):
    model = Post
    read_schema = PostRead
    write_schema = PostCreate
```

```python title="config/urls.py"
from buraq.views.viewsets import Router

from posts.api import PostViewSet

router = Router()
router.register("/api/posts", PostViewSet, basename="post")

urlpatterns = router.urls
```

That is the whole resource:

| Method | Path | Action | Route name |
|---|---|---|---|
| `GET` | `/api/posts` | `list` | `post_list` |
| `POST` | `/api/posts` | `create` | `post_create` |
| `GET` | `/api/posts/{pk}` | `retrieve` | `post_detail` |
| `PUT` `PATCH` | `/api/posts/{pk}` | `update` | `post_update` |
| `DELETE` | `/api/posts/{pk}` | `destroy` | `post_delete` |

`basename` defaults to the class name without `ViewSet`, lowercased.

## Schemas

`read_schema` shapes what goes out — declared as `list[...]` for `list` and
singular for the rest, so `/api/docs` describes each correctly. `write_schema`
validates what comes in, so a request cannot set a field it does not list.

Both are optional. Without them the actions return model instances and take the
request body as it arrives.

## Only what you define is routed

Removing an action removes its route. A read-only resource is a viewset without
the write actions:

```python
class PostViewSet(ModelViewSet):
    model = Post
    read_schema = PostRead

    create = None
    update = None
    destroy = None
```

```
GET /api/posts        200
GET /api/posts/1      200
POST /api/posts       405
```

There is no second list of permitted methods to keep in step with the class.

## Overriding an action

Any action is an ordinary coroutine. Override it and the route stays:

```python
class PostViewSet(ModelViewSet):
    model = Post
    read_schema = PostRead

    async def list(self, request, **kwargs):
        """Only published posts."""
        return await Post.objects.filter(is_published=True)
```

`self.request` and `self.kwargs` are available throughout.

## Filtering, search and ordering

Declare which fields the query string may reach. A parameter naming anything
else is ignored, so a caller cannot filter on a column the class did not offer.

```python
class PostViewSet(ModelViewSet):
    model = Post
    read_schema = PostRead

    filter_fields = ["status", "author_id"]   # ?status=draft
    search_fields = ["title", "body"]         # ?search=hello
    ordering_fields = ["created_at", "title"] # ?ordering=-created_at
    ordering = ["-created_at"]                # when the request names none
    paginate_by = 20                          # ?page=2
```

```
GET /api/posts?status=draft&search=hello&ordering=title&page=2
```

`search` matches case-insensitively across every field in `search_fields`, as
`OR`. `ordering` accepts a leading `-` to reverse. Anything outside
`ordering_fields` falls back to the class default rather than erroring.

## CSRF

CSRF protection is on by default and expects a token in a form body, which a
JSON client cannot send. A viewset serving an API needs to say so:

```python
class PostViewSet(ModelViewSet):
    csrf_exempt = True
    model = Post
```

Only exempt a resource that authenticates some other way — a bearer token, an
API key. Never one that relies on the session cookie.

## Custom actions

`ViewSet` has no actions of its own, so it routes exactly what you write:

```python
from buraq.views.viewsets import ViewSet


class StatusViewSet(ViewSet):
    async def list(self, request, **kwargs):
        return {"status": "ok"}
```

Only `list`, `create`, `retrieve`, `update` and `destroy` are routed. Anything
else on the class is a helper, reachable from those five.
