"""
Automatic permission creation.

Every concrete model gets add/change/delete/view permissions (configurable via
``Meta.default_permissions``) plus anything listed in ``Meta.permissions``.
Rows are created after ``migrate`` via the ``post_migrate`` signal, so
declaring a permission in Meta is enough to have the row exist.
"""

from __future__ import annotations

from buraq.core.db import Base


def iter_model_permissions():
    """
    Yield ``(model, codename, name)`` for every permission every concrete model
    declares. Abstract models have no table and proxies share their parent's, so
    neither contributes permissions of its own.
    """
    for mapper in Base.registry.mappers:
        model = mapper.class_
        opts = getattr(model, "_meta", None)
        if opts is None or opts.abstract or opts.proxy:
            continue
        for codename, name in opts.get_default_permissions():
            yield model, codename, name


async def create_permissions(verbosity: int = 1) -> int:
    """
    Create any missing ``Permission`` rows. Returns how many were created.

    Safe to run repeatedly — existing codenames are left untouched, so this can
    run after every migrate.
    """
    from sqlalchemy.exc import OperationalError, ProgrammingError

    from buraq.contrib.auth.models import Permission

    try:
        # Keyed by (content_type, codename): the codename alone is not unique,
        # so two apps each defining a Post both need their own "add_post" and
        # deduplicating on the codename gave the second one the first one's row.
        existing = {(p.content_type, p.codename) for p in await Permission.objects.all()}
    except (OperationalError, ProgrammingError):
        # A brand new project runs migrate before it has any migrations, so the
        # auth tables legitimately do not exist yet. Nothing to create, and
        # nothing worth alarming anyone with.
        if verbosity > 1:
            print("  auth tables not created yet; skipping permissions")
        return 0

    missing = []
    for model, codename, name in iter_model_permissions():
        opts = model._meta
        key = (opts.label_lower, codename)
        if key in existing:
            continue
        missing.append(
            {"name": name, "codename": codename, "content_type": opts.label_lower}
        )
        existing.add(key)
        if verbosity > 1:
            print(f"  created permission {opts.app_label}.{codename}")

    if not missing:
        return 0

    # One statement rather than an INSERT per row: a project with many models
    # generates four permissions each, and every one was a separate round trip.
    await Permission.objects.bulk_create(missing)

    if verbosity:
        # Imported here: this runs from the CLI, but the module is also imported
        # by applications that have no console attached.
        from buraq.management import console

        console.success(f"Created {len(missing)} permission(s)")
    return len(missing)


async def _on_post_migrate(sender, **kwargs):
    """``post_migrate`` receiver: create whichever permission rows are missing."""
    await create_permissions(kwargs.get("verbosity", 1))


def register() -> None:
    """Connect the ``post_migrate`` receiver. Called from the auth app config."""
    from buraq import signals

    signals.post_migrate.connect(_on_post_migrate)
