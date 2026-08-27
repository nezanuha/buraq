"""
End-to-end tests for automatic permission creation.

Verifies that ``Meta.permissions`` / ``Meta.default_permissions`` actually
produce ``Permission`` rows, not just codenames on ``_meta``.
"""

import pytest

# Imported at module scope on purpose: Base.metadata only contains tables for
# models that have already been imported, so create_all() below would otherwise
# skip buraq_permissions entirely.
from buraq.contrib.auth import models as _auth_models  # noqa: F401
from buraq.core.db import Base, engine


@pytest.fixture
async def db():
    from buraq.conf import settings
    from tests.conftest import use_test_database

    use_test_database(settings)
    settings.SECRET_KEY = "test-secret-key-for-permission-tests"

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_create_permissions_inserts_rows_for_every_model(db):
    from buraq.contrib.auth.models import Permission
    from buraq.contrib.auth.permissions import create_permissions

    created = await create_permissions(verbosity=0)
    assert created > 0

    codenames = {p.codename for p in await Permission.objects.all()}
    # The auth app's own models must be covered.
    assert {"add_user", "change_user", "delete_user", "view_user"} <= codenames


async def test_create_permissions_is_idempotent(db):
    from buraq.contrib.auth.models import Permission
    from buraq.contrib.auth.permissions import create_permissions

    first = await create_permissions(verbosity=0)
    total_after_first = len(await Permission.objects.all())

    second = await create_permissions(verbosity=0)
    total_after_second = len(await Permission.objects.all())

    assert first > 0
    assert second == 0, "re-running must not duplicate permissions"
    assert total_after_first == total_after_second


async def test_permission_content_type_uses_model_label(db):
    from buraq.contrib.auth.models import Permission
    from buraq.contrib.auth.permissions import create_permissions

    await create_permissions(verbosity=0)

    perm = await Permission.objects.get(codename="add_user")
    assert perm.content_type == "auth.user"
    # user_perm_str is what has_perm() expects.
    assert perm.user_perm_str == "auth.add_user"


async def test_app_config_ready_connects_post_migrate():
    from buraq import signals
    from buraq.contrib.auth.apps import AuthConfig

    before = len(signals.post_migrate._receivers)
    await AuthConfig().ready()
    assert len(signals.post_migrate._receivers) == before + 1
