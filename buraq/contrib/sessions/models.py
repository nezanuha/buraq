"""The table behind the database session backend.

A model rather than the block of CREATE TABLE the backend's docstring used to
ask you to run by hand: every other table Buraq owns arrives through ``buraq
migrate``, and there was no reason this one should be the exception. The key is
the session's own, so there is no surrogate id beside it.
"""

from __future__ import annotations

import sqlalchemy as sa

from buraq.orm.base import Model


class Session(Model):
    """One stored session, keyed by the value carried in the cookie."""

    __tablename__ = "buraq_sessions"

    session_key = sa.Column(sa.String(64), primary_key=True)
    session_data = sa.Column(sa.Text, nullable=False)
    # A POSIX timestamp rather than a datetime: the backend compares it against
    # time.time() on every read, and storing it as a float keeps that a
    # comparison rather than a conversion.
    expire_date = sa.Column(sa.Float, nullable=False, index=True)

    class Meta:
        app_label = "sessions"

    def __repr__(self) -> str:
        return f"<Session {self.session_key[:8]}…>"
