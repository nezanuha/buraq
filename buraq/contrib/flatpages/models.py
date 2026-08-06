"""Flat page model — database-backed static content pages."""
from __future__ import annotations

import sqlalchemy as sa

from buraq.orm.base import Model


class FlatPage(Model):
    """A simple page stored in the database, served at a fixed URL path."""

    __tablename__ = "flatpages_flatpage"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    url = sa.Column(sa.String(255), unique=True, nullable=False)
    title = sa.Column(sa.String(255), nullable=False)
    content = sa.Column(sa.Text, default="")
    enable_comments = sa.Column(sa.Boolean, default=False)
    template_name = sa.Column(sa.String(255), default="")
    registration_required = sa.Column(sa.Boolean, default=False)

    def __repr__(self):
        return f"<FlatPage {self.url!r}>"
