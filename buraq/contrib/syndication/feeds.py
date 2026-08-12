"""
Syndication framework — RSS 2.0 and Atom 1.0 feed generators.

Usage::

    from buraq.contrib.syndication import Feed
    from buraq.urls import get

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

    # Wire it up:
    get("/feed/rss/", LatestPostsFeed.as_feed(feed_type="rss"))
    get("/feed/atom/", LatestPostsFeed.as_feed(feed_type="atom"))
"""
from __future__ import annotations

import datetime
import xml.etree.ElementTree as ET
from typing import Any


# ── Low-level feed renderers ──────────────────────────────────────────────────

class _SyndicationFeed:
    """Base feed renderer — produces a serialized feed string."""

    mime_type: str = "application/xml; charset=utf-8"

    def __init__(
        self,
        title: str,
        link: str,
        description: str,
        language: str = "en",
        author: str | None = None,
        subtitle: str | None = None,
        categories: list[str] | None = None,
        feed_copyright: str | None = None,
        feed_guid: str | None = None,
        ttl: int | None = None,
    ) -> None:
        self.title = title
        self.link = link
        self.description = description
        self.language = language
        self.author = author
        self.subtitle = subtitle
        self.categories = categories or []
        self.feed_copyright = feed_copyright
        self.feed_guid = feed_guid
        self.ttl = ttl
        self._items: list[dict] = []

    def add_item(
        self,
        title: str,
        link: str,
        description: str,
        author: str | None = None,
        categories: list[str] | None = None,
        unique_id: str | None = None,
        pubdate: datetime.datetime | None = None,
        updateddate: datetime.datetime | None = None,
        enclosure: dict | None = None,
        **kwargs,
    ) -> None:
        self._items.append({
            "title": title,
            "link": link,
            "description": description,
            "author": author,
            "categories": categories or [],
            "unique_id": unique_id or link,
            "pubdate": pubdate,
            "updateddate": updateddate,
            "enclosure": enclosure,
            **kwargs,
        })

    def write(self, encoding: str = "utf-8") -> str:
        raise NotImplementedError

    @staticmethod
    def _rfc2822(dt: datetime.datetime) -> str:
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")

    @staticmethod
    def _iso8601(dt: datetime.datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class RssFeed(_SyndicationFeed):
    """RSS 2.0 feed renderer."""

    mime_type = "application/rss+xml; charset=utf-8"
    format = "rss"

    def write(self, encoding: str = "utf-8") -> str:
        rss = ET.Element("rss", version="2.0", attrib={
            "xmlns:atom": "http://www.w3.org/2005/Atom",
        })
        channel = ET.SubElement(rss, "channel")

        ET.SubElement(channel, "title").text = self.title
        ET.SubElement(channel, "link").text = self.link
        ET.SubElement(channel, "description").text = self.description
        ET.SubElement(channel, "language").text = self.language
        if self.author:
            ET.SubElement(channel, "managingEditor").text = self.author
        if self.feed_copyright:
            ET.SubElement(channel, "copyright").text = self.feed_copyright
        if self.ttl is not None:
            ET.SubElement(channel, "ttl").text = str(self.ttl)
        for cat in self.categories:
            ET.SubElement(channel, "category").text = cat

        ET.SubElement(channel, "atom:link", attrib={
            "href": self.link,
            "rel": "self",
            "type": "application/rss+xml",
        })

        for item in self._items:
            entry = ET.SubElement(channel, "item")
            ET.SubElement(entry, "title").text = item["title"]
            ET.SubElement(entry, "link").text = item["link"]
            ET.SubElement(entry, "description").text = item["description"]
            ET.SubElement(entry, "guid", isPermaLink="false").text = item["unique_id"]
            if item["author"]:
                ET.SubElement(entry, "author").text = item["author"]
            if item["pubdate"]:
                ET.SubElement(entry, "pubDate").text = self._rfc2822(item["pubdate"])
            for cat in item["categories"]:
                ET.SubElement(entry, "category").text = cat
            if item.get("enclosure"):
                enc = item["enclosure"]
                ET.SubElement(entry, "enclosure", attrib={
                    "url": enc["url"],
                    "length": str(enc.get("length", 0)),
                    "type": enc.get("mime_type", "audio/mpeg"),
                })

        ET.indent(rss)
        return ET.tostring(rss, encoding="unicode", xml_declaration=False)


class Atom1Feed(_SyndicationFeed):
    """Atom 1.0 feed renderer."""

    mime_type = "application/atom+xml; charset=utf-8"
    format = "atom"
    _ns = "http://www.w3.org/2005/Atom"

    def _el(self, parent, tag: str, text: str | None = None, **attrs) -> ET.Element:
        el = ET.SubElement(parent, f"{{{self._ns}}}{tag}", attrib=attrs)
        if text is not None:
            el.text = text
        return el

    def write(self, encoding: str = "utf-8") -> str:
        feed = ET.Element(f"{{{self._ns}}}feed")
        self._el(feed, "title", self.title)
        self._el(feed, "subtitle", self.description)
        self._el(feed, "link", href=self.link, rel="alternate")
        self._el(feed, "id", self.link)
        self._el(feed, "updated", self._iso8601(datetime.datetime.utcnow()))
        if self.author:
            auth = ET.SubElement(feed, f"{{{self._ns}}}author")
            self._el(auth, "name", self.author)
        for cat in self.categories:
            self._el(feed, "category", term=cat)
        if self.feed_copyright:
            self._el(feed, "rights", self.feed_copyright)

        for item in self._items:
            entry = ET.SubElement(feed, f"{{{self._ns}}}entry")
            self._el(entry, "title", item["title"])
            self._el(entry, "link", href=item["link"], rel="alternate")
            self._el(entry, "id", item["unique_id"])
            updated = item.get("updateddate") or item.get("pubdate") or datetime.datetime.utcnow()
            self._el(entry, "updated", self._iso8601(updated))
            if item.get("pubdate"):
                self._el(entry, "published", self._iso8601(item["pubdate"]))
            self._el(entry, "summary", item["description"])
            if item.get("author"):
                auth = ET.SubElement(entry, f"{{{self._ns}}}author")
                self._el(auth, "name", item["author"])
            for cat in item["categories"]:
                self._el(entry, "category", term=cat)

        ET.indent(feed)
        return ET.tostring(feed, encoding="unicode", xml_declaration=False)


# ── High-level Feed class (mirrors Django's Feed) ─────────────────────────────

class Feed:
    """
    Base class for feed views.

    Subclass and define ``title``, ``link``, ``description``, ``items()``,
    and optionally ``item_title()``, ``item_description()``, ``item_link()``.

    Then wire it up::

        get("/feed/", MyFeed.as_feed())
        get("/feed/rss/", MyFeed.as_feed(feed_type="rss"))
        get("/feed/atom/", MyFeed.as_feed(feed_type="atom"))
    """

    title: str = ""
    link: str = ""
    description: str = ""
    language: str = "en"
    author_name: str | None = None
    categories: list[str] = []
    feed_copyright: str | None = None
    ttl: int | None = None
    feed_type: type[_SyndicationFeed] = RssFeed

    # ── Override these in subclasses ──────────────────────────────────────────

    async def items(self) -> list[Any]:
        return []

    def item_title(self, item: Any) -> str:
        return str(item)

    def item_description(self, item: Any) -> str:
        return ""

    def item_link(self, item: Any) -> str:
        return self.link

    def item_pubdate(self, item: Any) -> datetime.datetime | None:
        return getattr(item, "created_at", None)

    def item_updateddate(self, item: Any) -> datetime.datetime | None:
        return getattr(item, "updated_at", None)

    def item_author(self, item: Any) -> str | None:
        return None

    def item_categories(self, item: Any) -> list[str]:
        return []

    def item_guid(self, item: Any) -> str:
        return self.item_link(item)

    # ── Internal ──────────────────────────────────────────────────────────────

    def get_feed(self, feed_type: type[_SyndicationFeed]) -> _SyndicationFeed:
        """Return a feed renderer instance with metadata populated."""
        return feed_type(
            title=self.title,
            link=self.link,
            description=self.description,
            language=self.language,
            author=self.author_name,
            categories=self.categories,
            feed_copyright=self.feed_copyright,
            ttl=self.ttl,
        )

    async def __call__(self, request, **kwargs):
        from starlette.responses import Response
        feed = self.get_feed(self.feed_type)
        for item in await self.items():
            feed.add_item(
                title=self.item_title(item),
                link=self.item_link(item),
                description=self.item_description(item),
                author=self.item_author(item),
                categories=self.item_categories(item),
                unique_id=self.item_guid(item),
                pubdate=self.item_pubdate(item),
                updateddate=self.item_updateddate(item),
            )
        content = feed.write()
        return Response(
            content=f'<?xml version="1.0" encoding="utf-8"?>\n{content}',
            media_type=feed.mime_type,
        )

    @classmethod
    def as_feed(cls, feed_type: str | type[_SyndicationFeed] = "rss"):
        """
        Return an ASGI-compatible view function for this feed.

        ``feed_type`` can be ``"rss"``, ``"atom"``, or a
        ``_SyndicationFeed`` subclass directly.
        """
        if isinstance(feed_type, str):
            feed_type = {"rss": RssFeed, "atom": Atom1Feed}[feed_type.lower()]

        async def view(request, **kwargs):
            instance = cls()
            instance.feed_type = feed_type
            return await instance(request, **kwargs)

        view.__name__ = f"{cls.__name__}_feed"
        return view
