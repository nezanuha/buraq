"""
Viewsets and a router — one class per model instead of five views and five routes.

A JSON resource is nearly always the same five actions over the same model, and
writing them out means five view functions, five `path()` calls and five names
kept in step by hand. A viewset states the model once; the router turns it into
the routes:

    class PostViewSet(ModelViewSet):
        model = Post
        read_schema = PostRead
        write_schema = PostCreate

    router = Router()
    router.register("/posts", PostViewSet, basename="post")

    urlpatterns = router.urls

    GET    /posts          post_list
    POST   /posts          post_create
    GET    /posts/<int:pk> post_detail
    PUT    /posts/<int:pk> post_update
    PATCH  /posts/<int:pk> post_update
    DELETE /posts/<int:pk> post_delete

Override any action to change it, and leave the rest generated. Anything the
viewset does not define is simply not routed, so a read-only resource is a
viewset with `create`, `update` and `destroy` removed.
"""
from __future__ import annotations

from typing import Any

from buraq.urls import URLPattern

__all__ = ["ViewSet", "ModelViewSet", "Router"]

#: action -> (url suffix, HTTP methods, url-name suffix). The order is the order
#: routes are registered, and fixed paths come before the one with a converter
#: in it so that /posts/new could never be read as a primary key.
_ROUTES: tuple[tuple[str, str, list[str], str], ...] = (
    ("list", "", ["GET"], "list"),
    ("create", "", ["POST"], "create"),
    ("retrieve", "/<int:pk>", ["GET"], "detail"),
    ("update", "/<int:pk>", ["PUT", "PATCH"], "update"),
    ("destroy", "/<int:pk>", ["DELETE"], "delete"),
)


class ViewSet:
    """Actions grouped on one class. Define only the ones the resource has."""

    #: Query parameters that filter the queryset by exact match.
    filter_fields: list[str] = []
    #: Fields a `?search=` term is matched against, case-insensitively.
    search_fields: list[str] = []
    #: Fields `?ordering=` may sort by. A leading "-" reverses.
    ordering_fields: list[str] = []
    #: Applied when the request names no ordering.
    ordering: list[str] = []
    #: Rows per page when `?page=` is given.
    paginate_by: int | None = None

    def __init__(self, request=None, **kwargs):
        self.request = request
        self.kwargs = kwargs

    @classmethod
    def as_view(cls, action: str):
        """A callable for one action, which is what a route needs."""

        async def view(request, **kwargs):
            return await getattr(cls(request, **kwargs), action)(request, **kwargs)

        view.__name__ = f"{cls.__name__}.{action}"
        view.__doc__ = (getattr(cls, action).__doc__ or "").strip() or None
        # view_class is what tells route registration to rebuild the signature
        # from the URL -- (request, pk: int) for a detail route, (request) for a
        # list one. Without it FastAPI reads **kwargs and asks for a query
        # parameter named "kwargs".
        view.view_class = cls
        view.view_initkwargs = {}
        # The CSRF middleware resolves the route to find this, so a viewset
        # marked exempt has to carry the mark onto the callable it hands over.
        if getattr(cls, "csrf_exempt", False):
            view._csrf_exempt = True
        return view


class ModelViewSet(ViewSet):
    """The five actions, implemented against ``model``.

    ``read_schema`` shapes what goes out and ``write_schema`` validates what
    comes in; without them the actions return model instances and accept the
    request body as it arrives, which FastAPI will still serialise.
    """

    model: Any = None
    read_schema: Any = None
    write_schema: Any = None

    # ── Queryset ────────────────────────────────────────────────────────────

    async def get_queryset(self):
        """The rows this viewset works over, before filtering."""
        if self.model is None:
            raise AttributeError(
                f"{type(self).__name__} needs a `model`, or its own get_queryset()."
            )
        return self.model.objects.all()

    def filter_queryset(self, queryset):
        """Apply ``?field=``, ``?search=`` and ``?ordering=`` from the request.

        Only the fields a viewset names are honoured, so a query parameter
        cannot reach a column the class did not offer.
        """
        params = getattr(self.request, "query_params", {}) or {}

        for field in self.filter_fields:
            if params.get(field) not in (None, ""):
                queryset = queryset.filter(**{field: params[field]})

        term = params.get("search")
        if term and self.search_fields:
            from buraq.orm.query import Q

            condition = Q(**{f"{self.search_fields[0]}__icontains": term})
            for field in self.search_fields[1:]:
                condition = condition | Q(**{f"{field}__icontains": term})
            queryset = queryset.filter(condition)

        requested = params.get("ordering")
        if requested and requested.lstrip("-") in self.ordering_fields:
            queryset = queryset.order_by(requested)
        elif self.ordering:
            queryset = queryset.order_by(*self.ordering)

        return queryset

    # ── Actions ─────────────────────────────────────────────────────────────

    async def list(self, request, **kwargs):
        """Every row, filtered and ordered by the query string."""
        queryset = self.filter_queryset(await self.get_queryset())
        if self.paginate_by:
            page = max(1, int((request.query_params or {}).get("page", 1) or 1))
            queryset = queryset.limit(self.paginate_by).offset((page - 1) * self.paginate_by)
        return await queryset

    async def retrieve(self, request, pk: int, **kwargs):
        """One row, or 404."""
        from buraq.shortcuts import get_object_or_404

        return await get_object_or_404(self.model, id=pk)

    async def create(self, request, **kwargs):
        """Create a row from the request body."""
        return await self.model.objects.create(**await self._payload(request))

    async def update(self, request, pk: int, **kwargs):
        """Update a row, 404 if it is not there."""
        from buraq.shortcuts import get_object_or_404

        await get_object_or_404(self.model, id=pk)
        await self.model.objects.update(pk, **await self._payload(request))
        return await get_object_or_404(self.model, id=pk)

    async def destroy(self, request, pk: int, **kwargs):
        """Delete a row, 404 if it is not there."""
        from buraq.shortcuts import get_object_or_404

        await get_object_or_404(self.model, id=pk)
        await self.model.objects.delete(pk)
        return {"deleted": pk}

    async def _payload(self, request) -> dict:
        """The request body, validated by ``write_schema`` when there is one."""
        data = await request.json()
        if self.write_schema is None:
            return dict(data)
        return self.write_schema(**data).model_dump(exclude_unset=True)


class Router:
    """Turns viewsets into ``urlpatterns``."""

    def __init__(self):
        self._patterns: list[URLPattern] = []

    def register(self, prefix: str, viewset: type[ViewSet], basename: str = "") -> None:
        """Route every action ``viewset`` defines, under ``prefix``.

        An action the class does not have is not routed, so removing `create`
        from a viewset is how a resource becomes read-only -- there is no
        separate list of permitted methods to keep in step with it.
        """
        if not issubclass(viewset, ViewSet):
            raise TypeError(f"{viewset.__name__} must subclass ViewSet.")

        prefix = "/" + prefix.strip("/")
        basename = basename or viewset.__name__.replace("ViewSet", "").lower()

        schema = getattr(viewset, "read_schema", None)
        for action, suffix, methods, name in _ROUTES:
            if not callable(getattr(viewset, action, None)):
                continue
            extra = {}
            if schema is not None and action != "destroy":
                # list returns many; the others return one. Declaring the
                # singular for list fails at response validation, not at
                # startup, so it would surface as a 500 on the first request.
                extra["response_model"] = list[schema] if action == "list" else schema
            self._patterns.append(
                URLPattern(
                    f"{prefix}{suffix}",
                    viewset.as_view(action),
                    f"{basename}_{name}",
                    methods,
                    extra,
                )
            )

    @property
    def urls(self) -> list[URLPattern]:
        """What to put in ``urlpatterns``."""
        return list(self._patterns)
