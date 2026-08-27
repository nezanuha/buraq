"""Initial schema for buraq.contrib.sessions.

The database session backend needed a ``buraq_sessions`` table, and the only
instructions for creating it were a block of CREATE TABLE in the backend's
docstring for you to run by hand. Every other table Buraq owns arrives through
``buraq migrate``; this one now does too.
"""

import sqlalchemy as sa

from alembic import op

revision = "buraq_sessions_0001"
down_revision = None
branch_labels = ("buraq_sessions",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buraq_sessions",
        sa.Column("session_key", sa.String(length=64), nullable=False),
        sa.Column("session_data", sa.Text(), nullable=False),
        sa.Column("expire_date", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("session_key"),
    )
    # Expired rows are cleared by scanning this column, and a session store is
    # read on every request that carries a cookie.
    op.create_index(
        "ix_buraq_sessions_expire_date", "buraq_sessions", ["expire_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_buraq_sessions_expire_date", table_name="buraq_sessions")
    op.drop_table("buraq_sessions")
