"""Initial schema for buraq.contrib.auth.

Ships with Buraq so the framework can evolve its own tables without every
project having to autogenerate a schema it does not own. Lives on its own
Alembic branch, applied only when the app is in INSTALLED_APPS.
"""

import sqlalchemy as sa

from alembic import op

revision = "buraq_auth_0001"
down_revision = None
branch_labels = ("buraq_auth",)
depends_on = None


def upgrade() -> None:
    op.create_table('buraq_groups',
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('buraq_permissions',
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('codename', sa.String(length=100), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codename')
    )
    op.create_table('buraq_users',
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('username', sa.String(length=150), nullable=False),
    sa.Column('first_name', sa.String(length=150), nullable=True),
    sa.Column('last_name', sa.String(length=150), nullable=True),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_staff', sa.Boolean(), nullable=False),
    sa.Column('is_superuser', sa.Boolean(), nullable=False),
    sa.Column('date_joined', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_buraq_users_email'), 'buraq_users', ['email'], unique=True)
    op.create_index(op.f('ix_buraq_users_username'), 'buraq_users', ['username'], unique=True)
    op.create_table('buraq_group_permissions',
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('permission_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['buraq_groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['permission_id'], ['buraq_permissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('buraq_user_groups',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['buraq_groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['buraq_users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('buraq_user_permissions',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('permission_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['buraq_permissions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['buraq_users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('buraq_user_permissions')
    op.drop_table('buraq_user_groups')
    op.drop_table('buraq_group_permissions')
    op.drop_index(op.f('ix_buraq_users_username'), table_name='buraq_users')
    op.drop_index(op.f('ix_buraq_users_email'), table_name='buraq_users')
    op.drop_table('buraq_users')
    op.drop_table('buraq_permissions')
    op.drop_table('buraq_groups')
