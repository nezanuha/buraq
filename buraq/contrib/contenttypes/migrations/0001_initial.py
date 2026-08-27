"""Initial schema for buraq.contrib.contenttypes.

Ships with Buraq so the framework can evolve its own tables without every
project having to autogenerate a schema it does not own. Lives on its own
Alembic branch, applied only when the app is in INSTALLED_APPS.
"""

import sqlalchemy as sa

from alembic import op

revision = "buraq_contenttypes_0001"
down_revision = None
branch_labels = ("buraq_contenttypes",)
depends_on = None


def upgrade() -> None:
    op.create_table('contenttypes_contenttype',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('app_label', sa.String(length=100), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('app_label', 'model')
    )


def downgrade() -> None:
    op.drop_table('contenttypes_contenttype')
