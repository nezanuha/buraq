"""Make a permission unique per content type rather than globally.

``codename`` carried a global unique constraint, so ``add_post`` could exist
only once in the whole database. Two apps may each define a ``Post``, and both
legitimately need their own ``add_post`` -- with the global constraint the
second app silently shared the first one's row, and granting the permission
granted it for both models with no way to tell them apart.

The pair that is actually unique is (content_type, codename), which is what
this swaps to.
"""

import sqlalchemy as sa

from alembic import op

revision = "buraq_auth_0002"
down_revision = "buraq_auth_0001"
branch_labels = None
depends_on = None


#: The original constraint was emitted by ``unique=True`` on the column, so it
#: has no name of its own and cannot be dropped by one. Handing Alembic a naming
#: convention lets it name the reflected constraint deterministically, which is
#: the documented way to alter an unnamed constraint.
_NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    # SQLite cannot drop or add a constraint in place; batch_alter_table copies
    # the table, which is also correct on every other backend.
    with op.batch_alter_table(
        "buraq_permissions", schema=None, naming_convention=_NAMING
    ) as batch:
        batch.drop_constraint("uq_buraq_permissions_codename", type_="unique")
        batch.create_unique_constraint(
            "uq_buraq_permissions_content_type_codename", ["content_type", "codename"]
        )


def downgrade() -> None:
    # Rows that were only distinguishable by content type collide under the
    # global constraint, so the duplicates have to go before it can be restored.
    op.execute(
        sa.text(
            "DELETE FROM buraq_permissions WHERE id NOT IN "
            "(SELECT MIN(id) FROM buraq_permissions GROUP BY codename)"
        )
    )
    with op.batch_alter_table(
        "buraq_permissions", schema=None, naming_convention=_NAMING
    ) as batch:
        batch.drop_constraint(
            "uq_buraq_permissions_content_type_codename", type_="unique"
        )
        batch.create_unique_constraint("uq_buraq_permissions_codename", ["codename"])
