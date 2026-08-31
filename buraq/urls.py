"""
URL configuration for Buraq — path(), include(), get(), post(), reverse().

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

# Re-exported: reverse() raises NoReverseMatch and resolve() raises Resolver404,
# so this is where a caller looks for them.
from buraq.exceptions import NoReverseMatch, Resolver404  # noqa: F401

_PATH_TYPE_MAP = {"int": int, "str": str, "slug": str, "uuid": str, "path": str}
_TYPED_PARAM_RE = re.compile(r"<(\w+):(\w+)>")


def _to_fastapi_path(url_path: str) -> str:
    """
    Convert ``<int:pk>`` path syntax → FastAPI/Starlette ``{pk}`` syntax.

    'posts/<int:pk>/'  → '/posts/{pk}'
    'blog/<slug:slug>' → '/blog/{slug}'
    '<str:name>/'      → '/{name}'
    '<uuid:uid>'       → '/{uid}'
    """
    converted = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", url_path)
    return "/" + converted.strip("/")


def _extract_param_types(url_path: str) -> dict:
    """Return {param_name: python_type} from a typed URL path like /posts/<int:pk>."""
    return {
        name: _PATH_TYPE_MAP.get(type_str, str)
        for type_str, name in _TYPED_PARAM_RE.findall(url_path)
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
    module_path: str | None
    _prefix: str = ""
    namespace: str = ""
    _inline_patterns: list = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────

def include(module_path_or_patterns, namespace: str = "") -> URLInclude:
    """
    Include urlpatterns from a module path string or an inline list of patterns.

    # Module path (standard):
    path('/auth', include('buraq.contrib.auth.urls'))

    # Inline list — useful when patterns are already imported:
    path('/auth', include(auth_patterns, namespace="auth"))
    """
    if isinstance(module_path_or_patterns, (list, tuple)):
        inc = URLInclude(module_path=None, namespace=namespace)
        inc._inline_patterns = list(module_path_or_patterns)
        return inc
    return URLInclude(module_path_or_patterns, namespace=namespace)


_ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]



def path(
    url_path: str,
    view_or_include: Any,
    kwargs: dict | None = None,
    name: str = "",
    **extra,
) -> Any:
    """
    Handles ALL HTTP methods by default, method dispatch is
    done inside the view (or CBV's dispatch()).

    path('/posts',           include('posts.urls'))         # include sub-app
    path('/posts/',          views.post_list)               # all methods
    path('/posts/<int:pk>',  views.post_detail, name='post_detail')
    path('/posts/',          views.post_list, {'flag': True})  # extra view kwargs
    path('/posts/',          views.post_list, methods=["GET", "POST"])  # explicit
    """
    from buraq.contrib.admin.site import _AdminURLs

    if isinstance(view_or_include, (URLInclude, _AdminURLs)):
        view_or_include._prefix = _to_fastapi_path(url_path)
        return view_or_include
    view = view_or_include
    if kwargs:
        view = functools.partial(view, **kwargs)
        functools.update_wrapper(view, view_or_include)
    return URLPattern(url_path, view, name, extra.pop("methods", _ALL_METHODS), extra)


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


# ── URL registry & reverse() ──────────────────────────────────────────────────

# name → FastAPI path string, e.g. "post_detail" → "/posts/{pk}"
_route_registry: dict[str, str] = {}

# Names registered under i18n_patterns() — get a language prefix prepended
_i18n_route_names: set[str] = set()

# Maps route name → prefix_default_language flag
_i18n_prefix_default: dict[str, bool] = {}


@dataclass
class I18nURLGroup:
    """Wraps URL patterns that should be served under a language prefix."""
    patterns: list
    prefix_default_language: bool = True


def i18n_patterns(*patterns: Any, prefix_default_language: bool = True) -> I18nURLGroup:
    """
    Mark URL patterns as language-prefixed.

    Routes inside this group are served at ``/{lang}/{path}`` automatically —
    ``LocaleMiddleware`` strips the prefix before routing, so your views stay clean.
    Named routes get registered in ``_i18n_route_names`` so that ``url_for()``
    can prepend the correct language prefix when generating links.

    Usage::

        from buraq.urls import path, i18n_patterns
        from buraq.contrib.i18n.views import set_language

        urlpatterns = [
            path("/i18n/set_language", set_language),   # NOT language-prefixed
            i18n_patterns(
                path("/",        views.home,    name="home"),
                path("/about",   views.about,   name="about"),
                path("/posts",   include("posts.urls")),
            ),
        ]

    Add the group to ``urlpatterns`` as a single element — with ``append()``,
    inside the list literal as shown above, or with ``+= [i18n_patterns(...)]``
    — not spread with ``*`` or added directly with ``+=``. The group carries
    ``prefix_default_language`` through to route registration, which a plain
    list of patterns has no way to hold; ``register_urlpatterns`` unwraps it
    when it finds one.
    """
    return I18nURLGroup(list(patterns), prefix_default_language=prefix_default_language)


def reverse_lazy(name: str, **path_params: Any):
    """
    Lazy version of reverse() — the URL is not computed until the result is used as a string.

    Useful as a class attribute default where the URL registry isn't yet populated::

        class MyView(View):
            success_url = reverse_lazy("post_list")
    """
    from buraq.utils.functional import lazy
    _lazy_reverse = lazy(reverse, str)
    return _lazy_reverse(name, **path_params)


class ResolverMatch:
    """Holds the result of a successful URL resolve() call."""

    def __init__(self, func, args: tuple, kwargs: dict, url_name: str = "", namespace: str = ""):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.url_name = url_name
        self.namespace = namespace
        self.view_name = f"{namespace}:{url_name}" if namespace else url_name

    def __repr__(self):
        return (
            f"ResolverMatch(func={self.func!r}, kwargs={self.kwargs!r},"
            f" url_name={self.url_name!r})"
        )


def resolve(path_str: str) -> ResolverMatch:
    """
    Resolve a URL path to its view function and kwargs.

    Raises `Resolver404` if no route matches.
    """

    for name, registered_path in _route_registry.items():
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", registered_path)
        m = re.fullmatch(pattern, path_str.rstrip("/") or "/")
        if m:
            namespace, _, url_name = name.rpartition(":")
            return ResolverMatch(
                func=None,
                args=(),
                kwargs=m.groupdict(),
                url_name=url_name or name,
                namespace=namespace,
            )
    raise Resolver404(f"No URL pattern matches {path_str!r}")


def re_path(regex: str, view: Any, name: str = "", **extra) -> URLPattern:
    """
    Register a URL with a raw regex pattern.

    Unlike path(), the pattern must be a full Python regex (anchored implicitly).
    Named groups (``(?P<pk>\\d+)``) become kwargs.

    Usage::

        from buraq.urls import re_path

        urlpatterns = [
            re_path(r"/articles/(?P<pk>[0-9]+)", views.article_detail, name="article_detail"),
        ]
    """
    # Convert named regex groups to FastAPI path params for registration
    fastapi_path = re.sub(r"\(\?P<(\w+)>[^)]+\)", r"{\1}", regex)
    fastapi_path = "/" + fastapi_path.lstrip("/")
    pattern = URLPattern.__new__(URLPattern)
    pattern.path = fastapi_path
    pattern.view = view
    pattern.name = name
    pattern.methods = _ALL_METHODS
    pattern.extra = extra
    pattern.param_types = {}
    return pattern


def reverse(name: str, **path_params: Any) -> str:
    """
    Return the URL path for a named route.

    For routes registered via ``i18n_patterns()``, automatically prepends
    the active language prefix (skipped for the default language).

    Usage::

        from buraq.urls import reverse

        reverse("home")                      # → "/"
        reverse("post_detail", pk=42)        # → "/posts/42"

        # Inside an Arabic request (active language = "ar"):
        reverse("about")                     # → "/ar/about"
        reverse("post_detail", pk=42)        # → "/ar/posts/42"
    """
    if name not in _route_registry:
        from buraq.exceptions import NoReverseMatch
        raise NoReverseMatch(f"No URL pattern with name {name!r}. Did you set name= on path()?")

    path_str = _route_registry[name]

    # Substitute {param} placeholders
    for key, value in path_params.items():
        path_str = path_str.replace(f"{{{key}}}", str(value))

    if name not in _i18n_route_names:
        return path_str

    from buraq.conf.defaults import settings
    from buraq.utils.translation import get_language

    default_lang: str = getattr(settings, "LANGUAGE_CODE", "en")
    lang = get_language()

    prefix_default = _i18n_prefix_default.get(name, True)
    if lang == default_lang and not prefix_default:
        return path_str

    if lang == default_lang:
        return path_str

    return f"/{lang}{path_str}"


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
    param_types carries URL type info (e.g. {"pk": int}) so FastAPI
    coerces the string path segment to the right Python type.
    """
    if not getattr(view, "view_class", None):
        return view

    path_params = _PATH_PARAM_RE.findall(full_path)

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


def register_urlpatterns(
    app: Any,
    patterns: list,
    prefix: str = "",
    _i18n: bool = False,
    _namespace: str = "",
    _prefix_default_language: bool = True,
) -> None:
    """Recursively register all URL patterns with a FastAPI app instance."""
    for item in patterns:
        if isinstance(item, I18nURLGroup):
            register_urlpatterns(
                app, item.patterns, prefix, _i18n=True,
                _namespace=_namespace,
                _prefix_default_language=item.prefix_default_language,
            )

        elif type(item).__name__ == "_AdminURLs":
            # Mounting the admin is three things -- importing each app's
            # admin.py, adding its routes, serving its assets -- and only here
            # is the application available to do them.
            from buraq.contrib.admin.views import get_admin_router

            item.site.prefix = (prefix + item._prefix).rstrip("/") or "/admin"
            item.site.autodiscover()
            app.include_router(
                get_admin_router(item.site), prefix=prefix + item._prefix
            )
            from buraq.contrib.admin.setup import _mount_admin_static

            _mount_admin_static(app)

        elif isinstance(item, URLInclude):
            if item.module_path is None:
                sub_patterns = item._inline_patterns
            else:
                module = importlib.import_module(item.module_path)
                sub_patterns = getattr(module, "urlpatterns", [])
            ns = item.namespace or _namespace
            register_urlpatterns(
                app, sub_patterns, prefix + item._prefix, _i18n=_i18n,
                _namespace=ns,
                _prefix_default_language=_prefix_default_language,
            )

        elif isinstance(item, URLPattern):
            full_path = (prefix + item.path).replace("//", "/") or "/"
            view = _inject_request(item.view)
            view = _patch_cbv_signature(view, full_path, item.param_types)
            kw = dict(item.extra)
            if item.name:
                reg_name = f"{_namespace}:{item.name}" if _namespace else item.name
                kw["name"] = reg_name
                _route_registry[reg_name] = full_path
                if _i18n:
                    _i18n_route_names.add(reg_name)
                    _i18n_prefix_default[reg_name] = _prefix_default_language
            if len(item.methods) == 1:
                # Single method — use the convenience decorator (app.get, app.post, etc.)
                getattr(app, item.methods[0].lower())(full_path, **kw)(view)
            else:
                # Multiple methods — register once with add_api_route
                app.add_api_route(full_path, view, methods=item.methods, **kw)
