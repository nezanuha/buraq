"""Sites framework — multi-domain support for a single Buraq installation."""
from __future__ import annotations

import sqlalchemy as sa

from buraq.orm.base import Model


class Site(Model):
    """Represents a website domain served by this installation."""

    __tablename__ = "sites_site"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    domain = sa.Column(sa.String(255), unique=True, nullable=False)
    name = sa.Column(sa.String(255), nullable=False)

    def __repr__(self):
        return f"<Site {self.domain!r}>"

    @classmethod
    async def get_current(cls, request=None) -> "Site | None":
        """Return the Site matching the request's Host header, or the first site."""
        if request is not None:
            host = request.headers.get("host", "").split(":")[0]
            site = await cls.objects.get_or_none(domain=host)
            if site:
                return site
        return await cls.objects.filter().first()
