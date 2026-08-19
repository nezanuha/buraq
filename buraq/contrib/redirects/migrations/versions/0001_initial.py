"""Initial schema for buraq.contrib.redirects.

Ships with Buraq so the framework can evolve its own tables without every
project having to autogenerate a schema it does not own. Lives on its own
Alembic branch, applied only when the app is in INSTALLED_APPS.
"""

import sqlalchemy as sa

from alembic import op

revision = "buraq_redirects_0001"
down_revision = None
branch_labels = ("buraq_redirects",)
depends_on = None


def upgrade() -> None:
    op.create_table('redirects_redirect',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('old_path', sa.String(length=255), nullable=False),
    sa.Column('new_path', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('old_path')
    )


def downgrade() -> None:
    op.drop_table('redirects_redirect')
