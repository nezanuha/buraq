---
title: "Feeds (RSS / Atom)"
description: "buraq.utils.feedgenerator generates RSS 2.0 and Atom 1.0 feeds with no external dependencies."
---

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

---

## Class-based `Feed` (syndication framework)

`buraq.contrib.syndication` provides a higher-level `Feed` class that works like a view:

```python
from buraq.contrib.syndication import Feed

class LatestPostsFeed(Feed):
    title = "My Blog"
    link = "/posts/"
    description = "Latest posts from my blog."

    async def items(self):
        return await Post.objects.order_by("-created_at").limit(10).all()

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.body

    def item_link(self, item):
        return f"/posts/{item.id}/"

    def item_pubdate(self, item):
        return item.created_at
```

Wire it up as a view:

```python
from buraq.urls import get

get("/feed/rss/",  LatestPostsFeed.as_feed("rss"))
get("/feed/atom/", LatestPostsFeed.as_feed("atom"))
```

`as_feed("rss")` instantiates an `RssFeed` renderer; `as_feed("atom")` uses `Atom1Feed`. Both return a `Response` with the correct `Content-Type` header.

### Customisation hooks

| Method | Return type | Description |
|---|---|---|
| `items()` | `list` | Items to include in the feed |
| `item_title(item)` | `str` | Title for one item |
| `item_description(item)` | `str` | Body/summary for one item |
| `item_link(item)` | `str` | Permalink for one item |
| `item_pubdate(item)` | `datetime \| None` | Publication date |
| `item_updateddate(item)` | `datetime \| None` | Last-updated date (Atom only) |
| `item_author(item)` | `str \| None` | Author name |
| `item_categories(item)` | `list[str]` | Category strings |
| `item_guid(item)` | `str` | Unique ID (defaults to `item_link`) |

### Feed-level attributes

```python
class MyFeed(Feed):
    title = "Site News"
    link = "/"
    description = "Updates from our site."
    language = "en"
    author_name = "Editorial Team"
    categories = ["news", "updates"]
    feed_copyright = "© 2026 My Site"
    ttl = 600   # RSS only — time-to-live in seconds
```
