"""Initial schema for buraq.contrib.flatpages.

Ships with Buraq so the framework can evolve its own tables without every
project having to autogenerate a schema it does not own. Lives on its own
Alembic branch, applied only when the app is in INSTALLED_APPS.
"""

import sqlalchemy as sa

from alembic import op

revision = "buraq_flatpages_0001"
down_revision = None
branch_labels = ("buraq_flatpages",)
depends_on = None


def upgrade() -> None:
    op.create_table('flatpages_flatpage',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('url', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('enable_comments', sa.Boolean(), nullable=True),
    sa.Column('template_name', sa.String(length=255), nullable=True),
    sa.Column('registration_required', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('url')
    )


def downgrade() -> None:
    op.drop_table('flatpages_flatpage')
