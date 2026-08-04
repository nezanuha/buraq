"""
Class-based views — like Django's django.views.View.
"""
import inspect

from starlette.responses import Response


class View:
    """
    Base class-based view.

    Usage:
        class PostView(View):
            async def get(self, request, pk: int):
                post = await get_object_or_404(Post, id=pk)
                return render(request, "posts/detail.html", {"post": post})

            async def post(self, request, pk: int):
                form = PostForm(data=dict(await request.form()))
                if form.is_valid():
                    await form.save()
                    return redirect("/posts/")
                return render(request, "posts/detail.html", {"form": form})

        # In urls.py:
        get("/<int:pk>",  PostView.as_view(), name="post_detail")
        post("/<int:pk>", PostView.as_view(), name="post_detail_post")
    """

    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options", "trace"]

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def as_view(cls, **initkwargs):
        """
        Return a plain async function that FastAPI can route to.
        The returned function's signature is introspectable so path params work.
        """
        # Collect path params from all HTTP method handlers

        async def async_view(request, **kwargs):
            self = cls(**initkwargs)
            self.request = request
            self.kwargs = kwargs
            return await self.dispatch(request, **kwargs)

        async_view.__name__ = cls.__name__
        async_view.__qualname__ = f"{cls.__qualname__}.as_view.<locals>.async_view"
        async_view.__doc__ = cls.__doc__
        async_view.view_class = cls
        async_view.view_initkwargs = initkwargs

        # Copy signature from the handler with the most path params so FastAPI
        # correctly injects path parameters for all HTTP methods.
        from starlette.requests import Request
        best_sig = None
        best_param_count = -1
        for method_name in cls.http_method_names:
            handler = getattr(cls, method_name, None)
            if handler is None:
                continue
            sig = inspect.signature(handler)
            path_params = [
                p for p in sig.parameters.values()
                if p.name not in ("self", "request", "kwargs")
                and p.kind not in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                )
            ]
            if len(path_params) > best_param_count:
                best_param_count = len(path_params)
                best_sig = sig

        if best_sig is not None:
            params = list(best_sig.parameters.values())
            req_param = inspect.Parameter(
                "request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request
            )
            new_params = [req_param] + [
                p for p in params
                if p.name not in ("self", "request")
                and p.kind not in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                )
            ]
            async_view.__signature__ = best_sig.replace(parameters=new_params)

        return async_view

    async def dispatch(self, request, **kwargs):
        method = request.method.lower()
        if method in self.http_method_names:
            handler = getattr(self, method, self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed
        return await handler(request, **kwargs)

    async def http_method_not_allowed(self, request, **kwargs):
        allowed = [m.upper() for m in self.http_method_names if hasattr(self, m)]
        return Response(
            status_code=405,
            headers={"Allow": ", ".join(allowed)},
        )

    async def options(self, request, **kwargs):
        allowed = [m.upper() for m in self.http_method_names if hasattr(self, m)]
        return Response(
            status_code=200,
            headers={"Allow": ", ".join(allowed), "Content-Length": "0"},
        )
