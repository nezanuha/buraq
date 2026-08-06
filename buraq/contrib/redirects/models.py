"""URL redirect model — database-driven 301/410 redirects."""
from __future__ import annotations

import sqlalchemy as sa

from buraq.orm.base import Model


class Redirect(Model):
    """
    A URL redirect rule stored in the database.

    old_path → new_path (301 permanent redirect).
    Leave new_path empty for a 410 Gone response.
    """

    __tablename__ = "redirects_redirect"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    old_path = sa.Column(sa.String(255), unique=True, nullable=False)
    new_path = sa.Column(sa.String(255), default="")

    def __repr__(self):
        return f"<Redirect {self.old_path!r} → {self.new_path!r}>"
