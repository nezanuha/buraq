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
    from buraq.contrib.auth.models import Permission

    existing = {p.codename for p in await Permission.objects.all()}

    created = 0
    for model, codename, name in iter_model_permissions():
        if codename in existing:
            continue
        opts = model._meta
        await Permission.objects.create(
            name=name,
            codename=codename,
            content_type=opts.label_lower,
        )
        existing.add(codename)
        created += 1
        if verbosity > 1:
            print(f"  created permission {opts.app_label}.{codename}")

    if verbosity and created:
        print(f"Created {created} permission(s).")
    return created


def _on_post_migrate(sender, **kwargs):
    """
    ``post_migrate`` receiver.

    The signal is synchronous while permission creation is async, so schedule it
    on a running loop when there is one and otherwise run it to completion.
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(create_permissions(kwargs.get("verbosity", 1)))
    else:
        loop.create_task(create_permissions(kwargs.get("verbosity", 1)))


def register() -> None:
    """Connect the ``post_migrate`` receiver. Called from the auth app config."""
    from buraq import signals

    signals.post_migrate.connect(_on_post_migrate)
