from fastapi import APIRouter


class Router(APIRouter):
    """
    Simple router — just set prefix and go.

    Usage:
        from buraq import Router

        router = Router("/posts")

        @router.get("/")
        async def list_posts():
            return await Post.objects.all()

        @router.post("/", status_code=201)
        async def create_post(data: PostCreate):
            return await Post.objects.create(**data.model_dump())
    """

    def __init__(self, prefix: str = "", tags: list[str] | None = None, **kwargs):
        auto_tag = prefix.strip("/").replace("/", " ").title() if prefix else "default"
        super().__init__(
            prefix=prefix,
            tags=tags or [auto_tag],
            **kwargs,
        )


# Backward-compatible alias
AppRouter = Router
