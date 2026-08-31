"""
One class per resource instead of five views, five routes and five names.

Writing a JSON resource by hand meant a view function per action, a path() per
view, and a name per path kept in step with both -- the same five lines for
every model in the project.
"""

import pytest

from buraq.urls import URLPattern
from buraq.views.viewsets import ModelViewSet, Router, ViewSet


class _Post:
    __name__ = "Post"


class Full(ModelViewSet):
    model = _Post


class ReadOnly(ModelViewSet):
    model = _Post
    create = None
    update = None
    destroy = None


def _routes(viewset, prefix="/posts", basename="post"):
    router = Router()
    router.register(prefix, viewset, basename=basename)
    return router.urls


# ── What gets routed ─────────────────────────────────────────────────────────

def test_every_action_becomes_a_route():
    routes = _routes(Full)
    assert [(r.path, r.methods, r.name) for r in routes] == [
        ("/posts", ["GET"], "post_list"),
        ("/posts", ["POST"], "post_create"),
        ("/posts/{pk}", ["GET"], "post_detail"),
        ("/posts/{pk}", ["PUT", "PATCH"], "post_update"),
        ("/posts/{pk}", ["DELETE"], "post_delete"),
    ]


def test_removing_an_action_removes_its_route():
    """A read-only resource is a viewset without the write actions.

    There is no second list of permitted methods to keep in step with the class.
    """
    names = [r.name for r in _routes(ReadOnly)]
    assert names == ["post_list", "post_detail"]


def test_fixed_paths_come_before_the_one_with_a_converter():
    """Otherwise /posts/new is read as a primary key named "new"."""
    paths = [r.path for r in _routes(Full)]
    assert paths.index("/posts") < paths.index("/posts/{pk}")


def test_the_basename_defaults_to_the_class():
    router = Router()
    router.register("/articles", Full)
    assert router.urls[0].name == "full_list"


def test_the_prefix_is_normalised():
    for prefix in ("posts", "/posts", "posts/", "/posts/"):
        assert _routes(Full, prefix)[0].path == "/posts"


def test_registering_something_that_is_not_a_viewset_is_refused():
    with pytest.raises(TypeError, match="ViewSet"):
        Router().register("/x", type("NotAViewSet", (), {}))


# ── Response models ──────────────────────────────────────────────────────────

class _Schema:
    pass


class WithSchema(ModelViewSet):
    model = _Post
    read_schema = _Schema


def test_list_declares_many_and_the_rest_declare_one():
    """Declaring the singular for list fails at response validation.

    That surfaces as a 500 on the first request rather than an error at
    startup, so it is worth being sure of here.
    """
    by_name = {r.name: r.extra.get("response_model") for r in _routes(WithSchema)}
    assert by_name["post_list"] == list[_Schema]
    assert by_name["post_detail"] is _Schema
    assert by_name["post_update"] is _Schema


def test_delete_declares_no_response_model():
    """It returns {"deleted": pk}, which is not the read schema."""
    by_name = {r.name: r.extra for r in _routes(WithSchema)}
    assert "response_model" not in by_name["post_delete"]


def test_no_schema_means_no_response_model():
    assert all(r.extra == {} for r in _routes(Full))


# ── The view callables ───────────────────────────────────────────────────────

def test_the_view_carries_its_class_for_signature_patching():
    """Route registration rebuilds the signature from the URL using this.

    Without it FastAPI reads **kwargs and demands a query parameter called
    "kwargs" on every route.
    """
    view = Full.as_view("list")
    assert view.view_class is Full
    assert view.view_initkwargs == {}


def test_csrf_exemption_reaches_the_callable():
    """The middleware resolves the route to find the mark, not the class."""

    class Exempt(ModelViewSet):
        csrf_exempt = True
        model = _Post

    assert getattr(Exempt.as_view("create"), "_csrf_exempt", False) is True
    assert getattr(Full.as_view("create"), "_csrf_exempt", False) is False


def test_a_viewset_without_a_model_says_so():
    class Bare(ModelViewSet):
        pass

    with pytest.raises(AttributeError, match="model"):
        import asyncio

        asyncio.run(Bare().get_queryset())


def test_urls_is_a_copy():
    """Callers put this in urlpatterns; mutating it must not reach the router."""
    router = Router()
    router.register("/posts", Full)
    urls = router.urls
    urls.append(URLPattern("/x", lambda r: None, "x", ["GET"], {}))
    assert len(router.urls) == 5


def test_a_plain_viewset_routes_only_what_it_defines():
    """ViewSet has no actions of its own -- nothing to route until you add one."""

    class Custom(ViewSet):
        async def list(self, request, **kwargs):
            return []

    assert [r.name for r in _routes(Custom, basename="thing")] == ["thing_list"]
