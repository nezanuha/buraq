"""
Async sitemap view — renders sitemap.xml using stdlib xml.etree.ElementTree (C accelerator).
"""
from __future__ import annotations

from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from starlette.requests import Request
from starlette.responses import Response


async def sitemap(
    request: Request,
    sitemaps: dict[str, Any],
    section: str | None = None,
) -> Response:
    """
    Render a sitemap.xml response.

    Wire it up in urls.py::

        from buraq.contrib.sitemaps import Sitemap
        from buraq.contrib.sitemaps.views import sitemap
        from buraq.urls import path
        from functools import partial

        class PostSitemap(Sitemap):
            async def items(self):
                return await Post.objects.filter(published=True)
            def location(self, post):
                return f"/posts/{post.slug}"

        sitemaps = {"posts": PostSitemap()}

        urlpatterns = [
            path("/sitemap.xml", partial(sitemap, sitemaps=sitemaps)),
        ]
    """
    if section is not None:
        if section not in sitemaps:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"No sitemap section: {section!r}")
        active = {section: sitemaps[section]}
    else:
        active = sitemaps

    all_urls: list[dict] = []
    for sitemap_obj in active.values():
        if callable(sitemap_obj) and not hasattr(sitemap_obj, "get_urls"):
            sitemap_obj = sitemap_obj()
        page_urls = await sitemap_obj.get_urls(request=request)
        all_urls.extend(page_urls)

    xml_bytes = _build_sitemap_xml(all_urls)
    return Response(content=xml_bytes, media_type="application/xml; charset=utf-8")


def _build_sitemap_xml(urls: list[dict]) -> bytes:
    """Build sitemap XML using ElementTree's C accelerator — fast, no extra deps."""
    urlset = Element(
        "urlset",
        xmlns="http://www.sitemaps.org/schemas/sitemap/0.9",
    )

    for url_info in urls:
        url_el = SubElement(urlset, "url")
        SubElement(url_el, "loc").text = url_info["location"]
        if url_info.get("lastmod"):
            SubElement(url_el, "lastmod").text = url_info["lastmod"]
        if url_info.get("changefreq"):
            SubElement(url_el, "changefreq").text = url_info["changefreq"]
        if url_info.get("priority"):
            SubElement(url_el, "priority").text = url_info["priority"]

    xml_str = tostring(urlset, encoding="unicode", xml_declaration=False)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str.encode("utf-8")
