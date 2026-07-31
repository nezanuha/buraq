"""
Django-style URL configuration for Buraq.

Usage:

    # posts/urls.py
    from buraq.urls import get, post, put, delete

    urlpatterns = [
        get('/',          views.list_posts,   name='post_list'),
        post('/',         views.create_post,  name='post_create',  status_code=201),
        get('/<int:pk>',  views.get_post,     name='post_detail'),
        put('/<int:pk>',  views.update_post,  name='post_update'),
        delete('/<int:pk>', views.delete_post, name='post_delete', status_code=204),
    ]

    # config/urls.py
    from buraq.urls import path, include

    urlpatterns = [
        path('/auth',  include('buraq.contrib.auth.urls')),
        path('/posts', include('posts.urls')),
    ]

    app.load_urls(urlpatterns)
"""

import functools
import importlib
import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

_DJANGO_TYPE_MAP = {"int": int, "str": str, "slug": str, "uuid": str, "path": str}
_DJANGO_PARAM_RE = re.compile(r"<(\w+):(\w+)>")


def _to_fastapi_path(django_path: str) -> str:
    """
    Convert Django URL syntax → FastAPI/Starlette syntax.

    'posts/<int:pk>/'  → '/posts/{pk}'
    'blog/<slug:slug>' → '/blog/{slug}'
    '<str:name>/'      → '/{name}'
    '<uuid:uid>'       → '/{uid}'
    """
    converted = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", django_path)
    return "/" + converted.strip("/")


def _extract_param_types(django_path: str) -> dict:
    """Return {param_name: python_type} from a Django-style URL path."""
    return {
        name: _DJANGO_TYPE_MAP.get(type_str, str)
        for type_str, name in _DJANGO_PARAM_RE.findall(django_path)
    }


@dataclass
class URLPattern:
    path: str
    view: Callable
    name: str = ""
    methods: list = field(default_factory=lambda: ["GET"])
    extra: dict = field(default_factory=dict)
    param_types: dict = field(init=False, default_factory=dict)

    def __post_init__(self):
        self.param_types = _extract_param_types(self.path)  # before conversion
        self.path = _to_fastapi_path(self.path)
        self.methods = [m.upper() for m in self.methods]


@dataclass
class URLInclude:
    module_path: str
    _prefix: str = ""


# ── Public API ────────────────────────────────────────────────────────────────

def include(module_path: str) -> URLInclude:
    """Include urlpatterns from another module — like Django's include()."""
    return URLInclude(module_path)


_ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def path(url_path: str, view_or_include: Any, name: str = "", **kwargs) -> Any:
    """
    Django-style: handles ALL HTTP methods by default, method dispatch is
    done inside the view (or CBV's dispatch()).

    path('/posts',           include('posts.urls'))   # include sub-app
    path('/posts/',          views.post_list)          # all methods
    path('/posts/<int:pk>',  views.post_detail, name='post_detail')
    path('/posts/',          views.post_list, methods=["GET", "POST"])  # explicit
    """
    if isinstance(view_or_include, URLInclude):
        view_or_include._prefix = _to_fastapi_path(url_path)
        return view_or_include
    return URLPattern(url_path, view_or_include, name, kwargs.pop("methods", _ALL_METHODS), kwargs)


def get(url_path: str, view: Callable, name: str = "", **kwargs) -> URLPattern:
    return URLPattern(url_path, view, name, ["GET"], kwargs)


def post(url_path: str, view: Callable, name: str = "", **kwargs) -> URLPattern:
    return URLPattern(url_path, view, name, ["POST"], kwargs)


def put(url_path: str, view: Callable, name: str = "", **kwargs) -> URLPattern:
    return URLPattern(url_path, view, name, ["PUT"], kwargs)


def patch(url_path: str, view: Callable, name: str = "", **kwargs) -> URLPattern:
    return URLPattern(url_path, view, name, ["PATCH"], kwargs)


def delete(url_path: str, view: Callable, name: str = "", **kwargs) -> URLPattern:
    return URLPattern(url_path, view, name, ["DELETE"], kwargs)


# ── Internal registration ─────────────────────────────────────────────────────

def _inject_request(view: Callable) -> Callable:
    """
    Wrap a view so FastAPI injects the Starlette Request object into a
    parameter named `request` that has no type annotation.

    This lets users write:
        async def my_view(request, pk: int): ...
    instead of:
        async def my_view(request: Request, pk: int): ...
    """
    from starlette.requests import Request

    sig = inspect.signature(view)
    params = list(sig.parameters.values())
    if not params:
        return view
    first = params[0]
    if first.name != "request" or first.annotation is not inspect.Parameter.empty:
        return view

    # Rebuild signature with Request annotation on the first param
    new_params = [first.replace(annotation=Request)] + params[1:]
    new_sig = sig.replace(parameters=new_params)

    if inspect.iscoroutinefunction(view):
        @functools.wraps(view)
        async def wrapper(*args, **kwargs):
            return await view(*args, **kwargs)
    else:
        @functools.wraps(view)
        async def wrapper(*args, **kwargs):
            return view(*args, **kwargs)

    wrapper.__signature__ = new_sig
    return wrapper


_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")


def _patch_cbv_signature(view: Callable, full_path: str, param_types: dict = None) -> Callable:
    """
    Re-patch a CBV as_view() wrapper's signature using the *actual* URL path
    params extracted from the registered path string (e.g. '/posts/{pk}/edit').

    CBV handlers often use **kwargs to receive path params, which means the
    as_view() signature patching in View.as_view() can't know the param names.
    Here we have the path, so we can build the exact signature FastAPI needs.
    param_types carries Django type info (e.g. {"pk": int}) so FastAPI
    coerces the string path segment to the right Python type.
    """
    if not getattr(view, "view_class", None):
        return view

    path_params = _PATH_PARAM_RE.findall(full_path)
    if not path_params:
        return view

    from starlette.requests import Request

    types = param_types or {}
    new_params = [
        inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request),
    ] + [
        inspect.Parameter(
            name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=types.get(name, inspect.Parameter.empty),
        )
        for name in path_params
    ]

    @functools.wraps(view)
    async def cbv_wrapper(request, **kwargs):
        return await view(request, **kwargs)

    cbv_wrapper.__signature__ = inspect.Signature(new_params)
    cbv_wrapper.view_class = view.view_class
    cbv_wrapper.view_initkwargs = getattr(view, "view_initkwargs", {})
    return cbv_wrapper


def register_urlpatterns(app: Any, patterns: list, prefix: str = "") -> None:
    """Recursively register all URL patterns with a FastAPI app instance."""
    for item in patterns:
        if isinstance(item, URLInclude):
            module = importlib.import_module(item.module_path)
            sub_patterns = getattr(module, "urlpatterns", [])
            register_urlpatterns(app, sub_patterns, prefix + item._prefix)

        elif isinstance(item, URLPattern):
            full_path = (prefix + item.path).replace("//", "/") or "/"
            view = _inject_request(item.view)
            view = _patch_cbv_signature(view, full_path, item.param_types)
            kw = dict(item.extra)
            if item.name:
                kw["name"] = item.name
            if len(item.methods) == 1:
                # Single method — use the convenience decorator (app.get, app.post, etc.)
                getattr(app, item.methods[0].lower())(full_path, **kw)(view)
            else:
                # Multiple methods — register once with add_api_route
                app.add_api_route(full_path, view, methods=item.methods, **kw)
