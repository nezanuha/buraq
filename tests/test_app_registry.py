"""
App loading: INSTALLED_APPS -> AppConfig -> ready() -> connected receivers.

Every link here was broken at once. Nothing called ``populate()`` or
``run_ready_hooks()``, so no ``ready()`` ran anywhere in the framework; the CLI
never located a settings module, so INSTALLED_APPS was empty for every command;
and ``_fire_signal`` dropped the coroutine ``Signal.send`` returns instead of
awaiting it. The visible symptom was that ``migrate`` created no permissions,
which no test noticed because each break alone is silent.
"""

import asyncio
import sys
import textwrap

import pytest

from buraq.apps import AppConfig, Apps, _appconfig_in, _config_for


def _write_app(root, name, apps_py=None, models_py=None):
    """Create an importable app package under `root`."""
    pkg = root / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    if apps_py is not None:
        (pkg / "apps.py").write_text(textwrap.dedent(apps_py), encoding="utf-8")
    if models_py is not None:
        (pkg / "models.py").write_text(textwrap.dedent(models_py), encoding="utf-8")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return pkg


@pytest.fixture
def app_dir(tmp_path, monkeypatch):
    """A directory on sys.path, with imports of its packages undone afterwards."""
    before = set(sys.modules)
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    for name in set(sys.modules) - before:
        del sys.modules[name]


# ─── Resolving an INSTALLED_APPS entry ────────────────────────────────────────

def test_entry_naming_a_config_class_is_used(app_dir):
    _write_app(app_dir, "shop", apps_py="""
        from buraq.apps import AppConfig

        class ShopConfig(AppConfig):
            name = "shop"
            verbose_name = "Shopping"
    """)

    config = _config_for("shop.apps.ShopConfig")

    assert type(config).__name__ == "ShopConfig"
    assert config.verbose_name == "Shopping"


def test_entry_naming_only_the_module_still_finds_its_config(app_dir):
    """
    Listing "shop" rather than "shop.apps.ShopConfig" used to fall back to a
    bare AppConfig, quietly dropping the app's ready() hook.
    """
    _write_app(app_dir, "shop", apps_py="""
        from buraq.apps import AppConfig

        class ShopConfig(AppConfig):
            name = "shop"
            verbose_name = "Shopping"
    """)

    config = _config_for("shop")

    assert type(config).__name__ == "ShopConfig"
    assert config.verbose_name == "Shopping"


def test_app_without_an_apps_module_still_registers(app_dir):
    _write_app(app_dir, "plain")

    config = _config_for("plain")

    assert type(config) is AppConfig
    assert config.label == "plain"


def test_default_flag_picks_between_several_configs(app_dir):
    _write_app(app_dir, "multi", apps_py="""
        from buraq.apps import AppConfig

        class BasicConfig(AppConfig):
            name = "multi"

        class FancyConfig(AppConfig):
            name = "multi"
            default = True
    """)

    assert _appconfig_in("multi").__name__ == "FancyConfig"


def test_ambiguous_configs_are_not_guessed_at(app_dir):
    _write_app(app_dir, "ambiguous", apps_py="""
        from buraq.apps import AppConfig

        class OneConfig(AppConfig):
            name = "ambiguous"

        class TwoConfig(AppConfig):
            name = "ambiguous"
    """)

    assert _appconfig_in("ambiguous") is None


def test_a_broken_apps_module_is_not_mistaken_for_a_missing_one(app_dir):
    """An ImportError inside apps.py must surface, not silently disable the app."""
    _write_app(app_dir, "broken", apps_py="""
        import a_module_that_does_not_exist  # noqa: F401
    """)

    with pytest.raises(ImportError):
        _appconfig_in("broken")


# ─── ready() ──────────────────────────────────────────────────────────────────

def test_ready_hooks_run(app_dir):
    _write_app(app_dir, "hooked", apps_py="""
        from buraq.apps import AppConfig

        calls = []

        class HookedConfig(AppConfig):
            name = "hooked"

            async def ready(self):
                calls.append(1)
    """)

    registry = Apps()
    registry.populate(["hooked"])
    asyncio.run(registry.run_ready_hooks())

    import hooked.apps

    assert hooked.apps.calls == [1]


def test_ready_hooks_run_only_once(app_dir):
    """Startup paths may both call setup(); ready() must not run twice."""
    _write_app(app_dir, "once", apps_py="""
        from buraq.apps import AppConfig

        calls = []

        class OnceConfig(AppConfig):
            name = "once"

            async def ready(self):
                calls.append(1)
    """)

    registry = Apps()
    registry.populate(["once"])
    asyncio.run(registry.run_ready_hooks())
    asyncio.run(registry.run_ready_hooks())

    import once.apps

    assert once.apps.calls == [1]


def test_models_are_imported_so_the_orm_registry_sees_them(app_dir):
    _write_app(app_dir, "withmodels", models_py="""
        loaded = True
    """)

    registry = Apps()
    registry.populate(["withmodels"])
    registry.import_models()

    assert sys.modules["withmodels.models"].loaded is True


def test_import_models_tolerates_an_app_without_models(app_dir):
    _write_app(app_dir, "modelless")

    registry = Apps()
    registry.populate(["modelless"])
    registry.import_models()  # must not raise


# ─── Engine configuration ─────────────────────────────────────────────────────

def test_sql_echo_is_off_unless_asked_for():
    """
    Echo used to follow DEBUG, so every management command printed the SQL it
    ran and buried its own output in it.
    """
    from buraq.conf import settings

    assert settings.DATABASE_ECHO is False


def test_the_engine_reads_the_echo_setting(monkeypatch):
    import buraq.core.db as db
    from buraq.conf import settings

    captured = {}

    def fake_create_async_engine(url, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(db, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(settings, "DATABASE_ECHO", True)
    db._make_engine()

    assert captured["echo"] is True


# ─── Tables migrations must not touch ─────────────────────────────────────────

def test_raw_sql_tables_are_hidden_from_autogenerate():
    """
    The database cache backend creates its table with raw SQL, so it is absent
    from Base.metadata -- and autogenerate drops what it cannot see. A project
    using that backend got a migration deleting its live store.
    """
    from buraq.core.db import tables_migrations_ignore

    assert "buraq_cache_table" in tables_migrations_ignore()


def test_the_session_table_is_a_model_not_a_hidden_one():
    """
    buraq_sessions used to be created by SQL in a docstring, and was hidden from
    autogenerate for the same reason as the cache table. It ships a migration
    now, so it belongs to the framework rather than being invisible.
    """
    import buraq.contrib.sessions.models  # noqa: F401
    from buraq.core.db import framework_table_names, tables_migrations_ignore

    assert "buraq_sessions" in framework_table_names()
    # Still not autogenerated by a project -- but because Buraq owns it now.
    assert "buraq_sessions" in tables_migrations_ignore()


def test_the_cache_table_name_follows_the_setting(monkeypatch):
    from buraq.conf import settings
    from buraq.core.db import tables_migrations_ignore

    monkeypatch.setattr(settings, "CACHE_TABLE", "my_cache", raising=False)

    assert "my_cache" in tables_migrations_ignore()


def test_unmanaged_models_are_still_ignored(monkeypatch):
    import buraq.core.db as db

    monkeypatch.setattr(db, "unmanaged_table_names", lambda: {"legacy_view"})

    assert "legacy_view" in db.tables_migrations_ignore()


# ─── configure(): the sync entry point alembic's env.py uses ──────────────────

def test_configure_loads_settings_and_models(tmp_path, monkeypatch):
    """
    env.py runs in its own process where nothing has loaded the project's
    settings, so Base.metadata was empty and a new project could never
    autogenerate its first migration.
    """
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "config" / "settings.py").write_text(
        'INSTALLED_APPS = ["cfgapp"]\n', encoding="utf-8"
    )
    _write_app(tmp_path, "cfgapp", models_py="loaded = True\n")

    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    import buraq.apps as apps_module
    from buraq.apps import Apps, configure

    monkeypatch.setattr(apps_module, "apps", Apps())
    configure()

    assert sys.modules["cfgapp.models"].loaded is True
    assert apps_module.apps.is_installed("cfgapp")


def test_the_database_cache_uses_the_configured_table(monkeypatch):
    """
    CACHE_TABLE was documented by the backend but read by nothing: the table
    name came from a module constant, so setting it had no effect.
    """
    from buraq.conf import settings
    from buraq.contrib.cache.backends.db import DatabaseCache

    monkeypatch.setattr(settings, "CACHE_TABLE", "custom_cache")

    assert DatabaseCache()._table == "custom_cache"


def test_an_explicit_cache_table_beats_the_setting(monkeypatch):
    """CACHES OPTIONS pass the table directly; that must still win."""
    from buraq.conf import settings
    from buraq.contrib.cache.backends.db import DatabaseCache

    monkeypatch.setattr(settings, "CACHE_TABLE", "from_settings")

    assert DatabaseCache(table="from_options")._table == "from_options"


def test_static_serving_can_be_turned_off(monkeypatch):
    """
    Every other built-in can be removed -- the admin from urlpatterns, sessions
    and auth from MIDDLEWARE -- but static mounting had no switch: STATIC_DIR =
    None falls back to ./static, which a scaffolded project has.
    """
    from buraq.conf import settings
    from buraq.core.application import Buraq

    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:", raising=False)
    monkeypatch.setattr(settings, "SECRET_KEY", "x" * 32, raising=False)
    monkeypatch.setattr(settings, "INSTALLED_APPS", [], raising=False)
    monkeypatch.setattr(settings, "ROOT_URLCONF", None, raising=False)
    monkeypatch.setattr(settings, "SERVE_STATIC", False, raising=False)

    mounts = [r.path for r in Buraq().routes if type(r).__name__ == "Mount"]

    assert mounts == []


def test_production_static_actually_serves(tmp_path, monkeypatch):
    """
    The production path used to mount WhiteNoise, which is WSGI: mounting it in
    an ASGI application raised TypeError on the first request. Nobody hit it
    because whitenoise was not a dependency, so the ImportError fallback ran.
    """
    from fastapi.testclient import TestClient

    from buraq.conf import settings
    from buraq.core.application import Buraq

    static = tmp_path / "static"
    static.mkdir()
    (static / "a.css").write_text("body{}", encoding="utf-8")

    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:", raising=False)
    monkeypatch.setattr(settings, "SECRET_KEY", "x" * 32, raising=False)
    monkeypatch.setattr(settings, "INSTALLED_APPS", [], raising=False)
    monkeypatch.setattr(settings, "ROOT_URLCONF", None, raising=False)
    monkeypatch.setattr(settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(settings, "SERVE_STATIC", True, raising=False)
    monkeypatch.setattr(settings, "STATIC_DIR", str(static), raising=False)

    with TestClient(Buraq()) as client:
        response = client.get("/static/a.css")

    assert response.status_code == 200
    # Cache-Control is the point: ETag alone still costs a round trip per asset.
    cache_control = response.headers["cache-control"]
    assert "max-age=" in cache_control
    # This settings fixture leaves the default storage in place, which does not
    # hash names, so the same URL will serve new bytes after the next deploy and
    # the response must not promise otherwise.
    assert "immutable" not in cache_control
