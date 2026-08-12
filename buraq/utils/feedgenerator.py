"""
RSS 2.0 and Atom 1.0 feed generation. No external dependencies.

Usage:
    from buraq.utils.feedgenerator import Rss201rev2Feed, Atom1Feed
    from datetime import datetime, timezone

    feed = Rss201rev2Feed(
        title="My Blog",
        link="https://example.com",
        description="Latest posts",
        language="en",
    )
    feed.add_item(
        title="Hello World",
        link="https://example.com/hello",
        description="My first post",
        pubdate=datetime.now(timezone.utc),
        unique_id="https://example.com/hello",
    )
    xml_string = feed.writeString("utf-8")
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import format_datetime


def _rfc2822(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return format_datetime(dt)


def _iso8601(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


class SyndicationFeed:
    def __init__(self, title, link, description, *, language=None, author_name=None,
                 author_email=None, subtitle=None, categories=(),
                 feed_url=None, feed_copyright=None, ttl=None):
        self.feed = {
            "title": title, "link": link, "description": description,
            "language": language, "author_name": author_name,
            "author_email": author_email, "subtitle": subtitle,
            "categories": list(categories), "feed_url": feed_url,
            "feed_copyright": feed_copyright, "ttl": ttl,
        }
        self.items: list[dict] = []

    def add_item(self, title, link, description, *, author_name=None, author_email=None,
                 pubdate=None, unique_id=None, unique_id_is_permalink=False,
                 categories=(), item_copyright=None, ttl=None, **kwargs):
        self.items.append({
            "title": title, "link": link, "description": description,
            "author_name": author_name, "author_email": author_email,
            "pubdate": pubdate, "unique_id": unique_id,
            "unique_id_is_permalink": unique_id_is_permalink,
            "categories": list(categories), "item_copyright": item_copyright,
            "ttl": ttl, **kwargs,
        })

    def latest_post_date(self) -> datetime | None:
        dates = [i["pubdate"] for i in self.items if i.get("pubdate")]
        return max(dates) if dates else None

    def writeString(self, encoding: str = "utf-8") -> str:
        raise NotImplementedError


class Rss201rev2Feed(SyndicationFeed):
    """RSS 2.0.1 feed."""

    def writeString(self, encoding: str = "utf-8") -> str:
        rss = ET.Element("rss", version="2.0", **{"xmlns:atom": "http://www.w3.org/2005/Atom"})
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = self.feed["title"]
        ET.SubElement(channel, "link").text = self.feed["link"]
        ET.SubElement(channel, "description").text = self.feed["description"]
        if self.feed.get("language"):
            ET.SubElement(channel, "language").text = self.feed["language"]
        if self.feed.get("feed_url"):
            ET.SubElement(channel, "atom:link", href=self.feed["feed_url"],
                          rel="self", type="application/rss+xml")
        if self.feed.get("feed_copyright"):
            ET.SubElement(channel, "copyright").text = self.feed["feed_copyright"]
        latest = self.latest_post_date()
        if latest:
            ET.SubElement(channel, "lastBuildDate").text = _rfc2822(latest)
        if self.feed.get("ttl"):
            ET.SubElement(channel, "ttl").text = str(self.feed["ttl"])
        for item in self.items:
            el = ET.SubElement(channel, "item")
            ET.SubElement(el, "title").text = item["title"]
            ET.SubElement(el, "link").text = item["link"]
            ET.SubElement(el, "description").text = item["description"]
            if item.get("author_email") and item.get("author_name"):
                ET.SubElement(el, "author").text = f'{item["author_email"]} ({item["author_name"]})'
            if item.get("pubdate"):
                ET.SubElement(el, "pubDate").text = _rfc2822(item["pubdate"])
            if item.get("unique_id"):
                ET.SubElement(el, "guid",
                              isPermaLink=str(item["unique_id_is_permalink"]).lower()
                              ).text = item["unique_id"]
            for cat in item.get("categories", []):
                ET.SubElement(el, "category").text = cat
            if item.get("item_copyright"):
                ET.SubElement(el, "copyright").text = item["item_copyright"]
        return ET.tostring(rss, encoding="unicode")


class Atom1Feed(SyndicationFeed):
    """Atom 1.0 feed."""

    _ns = "http://www.w3.org/2005/Atom"

    def _tag(self, name: str) -> str:
        return f"{{{self._ns}}}{name}"

    def writeString(self, encoding: str = "utf-8") -> str:
        t = self._tag
        root = ET.Element(t("feed"))
        ET.SubElement(root, t("title")).text = self.feed["title"]
        ET.SubElement(root, t("link"), href=self.feed["link"], rel="alternate")
        if self.feed.get("feed_url"):
            ET.SubElement(root, t("link"), href=self.feed["feed_url"], rel="self")
        ET.SubElement(root, t("id")).text = self.feed["link"]
        if self.feed.get("subtitle"):
            ET.SubElement(root, t("subtitle")).text = self.feed["subtitle"]
        latest = self.latest_post_date()
        ET.SubElement(root, t("updated")).text = _iso8601(latest or datetime.now(UTC))
        if self.feed.get("author_name"):
            author = ET.SubElement(root, t("author"))
            ET.SubElement(author, t("name")).text = self.feed["author_name"]
            if self.feed.get("author_email"):
                ET.SubElement(author, t("email")).text = self.feed["author_email"]
        for item in self.items:
            entry = ET.SubElement(root, t("entry"))
            ET.SubElement(entry, t("title")).text = item["title"]
            ET.SubElement(entry, t("link"), href=item["link"], rel="alternate")
            ET.SubElement(entry, t("id")).text = item.get("unique_id") or item["link"]
            ET.SubElement(entry, t("updated")).text = _iso8601(
                item["pubdate"] if item.get("pubdate") else datetime.now(UTC)
            )
            ET.SubElement(entry, t("summary")).text = item["description"]
            if item.get("author_name"):
                author = ET.SubElement(entry, t("author"))
                ET.SubElement(author, t("name")).text = item["author_name"]
                if item.get("author_email"):
                    ET.SubElement(author, t("email")).text = item["author_email"]
            for cat in item.get("categories", []):
                ET.SubElement(entry, t("category"), term=cat)
            if item.get("item_copyright"):
                ET.SubElement(entry, t("rights")).text = item["item_copyright"]
        return ET.tostring(root, encoding="unicode")


DefaultFeed = Rss201rev2Feed
