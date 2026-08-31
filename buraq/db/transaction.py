"""Transaction control — ``buraq.db.transaction``.

The implementation lives in :mod:`buraq.orm.transaction`, next to the query code
it wraps. This is the name to import it by, so everything about the database is
reachable under ``buraq.db``:

    from buraq.db.transaction import atomic, on_commit

``buraq/db/__init__.py`` already re-exported the module as an attribute, which
made ``from buraq.db import transaction`` work and
``from buraq.db.transaction import atomic`` fail -- an attribute is not a
submodule, and the documentation used the second form.
"""

from buraq.orm.transaction import (  # noqa: F401
    TransactionManagementError,
    atomic,
    non_atomic,
    on_commit,
)

__all__ = [
    "atomic",
    "non_atomic",
    "on_commit",
    "TransactionManagementError",
]
