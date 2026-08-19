"""Initial schema for buraq.contrib.sites.

Ships with Buraq so the framework can evolve its own tables without every
project having to autogenerate a schema it does not own. Lives on its own
Alembic branch, applied only when the app is in INSTALLED_APPS.
"""

import sqlalchemy as sa

from alembic import op

revision = "buraq_sites_0001"
down_revision = None
branch_labels = ("buraq_sites",)
depends_on = None


def upgrade() -> None:
    op.create_table('sites_site',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('domain', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('domain')
    )


def downgrade() -> None:
    op.drop_table('sites_site')
