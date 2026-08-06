# Feeds (RSS / Atom)

`buraq.utils.feedgenerator` generates RSS 2.0 and Atom 1.0 feeds with no external dependencies.

## Basic RSS feed

```python
from datetime import datetime, timezone
from buraq.utils.feedgenerator import Rss201rev2Feed

feed = Rss201rev2Feed(
    title="My Blog",
    link="https://example.com",
    description="Latest posts from My Blog",
    language="en",
    feed_url="https://example.com/feed.rss",
)

feed.add_item(
    title="Hello World",
    link="https://example.com/hello",
    description="My first post.",
    pubdate=datetime.now(timezone.utc),
    unique_id="https://example.com/hello",
    author_name="Alice",
    author_email="alice@example.com",
    categories=["python", "web"],
)

xml = feed.writeString("utf-8")
```

## Atom feed

```python
from buraq.utils.feedgenerator import Atom1Feed

feed = Atom1Feed(
    title="My Blog",
    link="https://example.com",
    description="Latest posts",
    subtitle="Thoughts on async Python",
    author_name="Alice",
    feed_url="https://example.com/feed.atom",
)
feed.add_item(...)
xml = feed.writeString()
```

## Feed view

```python
from starlette.requests import Request
from starlette.responses import Response
from buraq.utils.feedgenerator import Rss201rev2Feed

async def rss_feed(request: Request) -> Response:
    posts = await Post.objects.filter(published=True).order_by("-created_at").limit(20).all()

    feed = Rss201rev2Feed(
        title="My Blog",
        link=str(request.base_url),
        description="Latest posts",
    )
    for post in posts:
        feed.add_item(
            title=post.title,
            link=str(request.base_url) + f"posts/{post.slug}",
            description=post.excerpt,
            pubdate=post.created_at,
            unique_id=str(post.id),
        )

    return Response(
        content=feed.writeString(),
        media_type="application/rss+xml; charset=utf-8",
    )
```

## `add_item()` parameters

| Parameter | Description |
|---|---|
| `title` | Item title |
| `link` | Permalink URL |
| `description` | Summary or full content |
| `pubdate` | `datetime` (timezone-aware recommended) |
| `unique_id` | GUID/ID — defaults to `link` in Atom |
| `unique_id_is_permalink` | Whether the GUID is a permalink (RSS) |
| `author_name` | Author display name |
| `author_email` | Author email |
| `categories` | List of category strings |
| `item_copyright` | Copyright notice |
