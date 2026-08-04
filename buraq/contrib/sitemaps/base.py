"""
Sitemap framework — Sitemap, GenericSitemap, and async sitemap view.

Usage:
    from buraq.contrib.sitemaps import Sitemap, GenericSitemap
"""
from __future__ import annotations

import inspect
from collections.abc import Callable
from datetime import date, datetime
from typing import Any


class Sitemap:
    """
    Base sitemap class. Subclass and override ``items()`` and optionally
    ``location()``, ``lastmod()``, ``changefreq()``, and ``priority()``.

    Usage::

        from buraq.contrib.sitemaps import Sitemap

        class PostSitemap(Sitemap):
            changefreq = "weekly"
            priority = 0.8

            async def items(self):
                return await Post.objects.filter(published=True)

            def lastmod(self, post):
                return post.updated_at

            def location(self, post):
                return f"/posts/{post.slug}"
    """

    changefreq: str | Callable | None = None
    priority: float | Callable | None = None
    protocol: str = "https"
    limit: int = 50_000
    i18n: bool = False

    def items(self) -> list:
        return []

    def location(self, item: Any) -> str:
        if hasattr(item, "get_absolute_url"):
            return item.get_absolute_url()
        return str(item)

    def lastmod(self, item: Any) -> datetime | date | None:
        return None

    def _get_changefreq(self, item: Any) -> str | None:
        cf = self.changefreq
        return cf(item) if callable(cf) else cf

    def _get_priority(self, item: Any) -> str | None:
        p = self.priority
        val = p(item) if callable(p) else p
        return str(val) if val is not None else None

    async def get_urls(
        self,
        page: int = 1,
        request: Any = None,
        protocol: str | None = None,
    ) -> list[dict[str, str | None]]:
        proto = protocol or self.protocol

        items = self.items()
        # Support async items() methods and awaitable querysets
        if inspect.isawaitable(items):
            items = await items

        page_items = items[(page - 1) * self.limit : page * self.limit]

        urls = []
        for item in page_items:
            loc = self.location(item)
            if not loc.startswith(("http://", "https://")):
                host = request.headers.get("host", "") if request else ""
                loc = f"{proto}://{host}{loc}"

            lastmod = self.lastmod(item)
            if isinstance(lastmod, datetime):
                lastmod_str: str | None = lastmod.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            elif isinstance(lastmod, date):
                lastmod_str = lastmod.strftime("%Y-%m-%d")
            else:
                lastmod_str = None

            urls.append({
                "location": loc,
                "lastmod": lastmod_str,
                "changefreq": self._get_changefreq(item),
                "priority": self._get_priority(item),
            })

        return urls


class GenericSitemap(Sitemap):
    """
    Sitemap for a model queryset.

    Usage::

        from buraq.contrib.sitemaps import GenericSitemap

        info_dict = {
            "queryset": Post.objects.filter(published=True),
            "date_field": "updated_at",
        }

        sitemaps = {
            "posts": GenericSitemap(info_dict, priority=0.6, changefreq="daily"),
        }
    """

    def __init__(
        self,
        info_dict: dict,
        priority: float | None = None,
        changefreq: str | None = None,
        protocol: str | None = None,
    ) -> None:
        self._queryset = info_dict["queryset"]
        self._date_field: str | None = info_dict.get("date_field")
        if priority is not None:
            self.priority = priority
        if changefreq is not None:
            self.changefreq = changefreq
        if protocol is not None:
            self.protocol = protocol

    def items(self):
        return self._queryset

    def lastmod(self, item: Any) -> datetime | date | None:
        if self._date_field:
            return getattr(item, self._date_field, None)
        return None

    def location(self, item: Any) -> str:
        if hasattr(item, "get_absolute_url"):
            return item.get_absolute_url()
        return str(item)


async def sitemap_index(request: Any, sitemaps: dict) -> Any:
    """
    Return a ``<sitemapindex>`` XML document with one ``<sitemap>`` entry per
    key in *sitemaps*.  Pass *sitemaps* via path kwargs or call directly.

    Usage::

        from buraq.contrib.sitemaps import sitemap_index, PostSitemap

        path("/sitemap.xml", sitemap_index, {"sitemaps": {"posts": PostSitemap()}})
    """
    from starlette.responses import Response

    proto = "https"
    host = request.headers.get("host", "") if request else ""

    entries: list[str] = []
    for section in sitemaps:
        loc = f"{proto}://{host}/sitemap-{section}.xml"
        entries.append(f"  <sitemap><loc>{loc}</loc></sitemap>")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</sitemapindex>"
    )
    return Response(content=xml, media_type="application/xml")
