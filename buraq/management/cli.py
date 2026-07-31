import shutil
import subprocess
from pathlib import Path

import typer

app = typer.Typer(
    name="buraq",
    help="Buraq management CLI — mirrors Django's manage.py",
    add_completion=False,
)

# ─── Dev Server ──────────────────────────────────────────────────────────────

@app.command()
def runserver(
    bind: str = typer.Argument(
        "main:app",
        help=(
            "ASGI app path ('main:app'), port number ('8080'), "
            "or host:port ('0.0.0.0:8080'). Defaults to main:app on port 8000."
        ),
    ),
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(True, help="Auto-reload on change"),
    workers: int = typer.Option(1, help="Number of worker processes"),
):
    """Start the development server (like Django's runserver)."""
    app_path = "main:app"

    # Django-style: runserver 8001  OR  runserver 0.0.0.0:8001
    if bind.isdigit():
        port = int(bind)
    elif ":" in bind and not bind.startswith("/") and "." not in bind.split(":")[0]:
        # looks like host:port, not a Python module path (module paths use dots)
        _h, _p = bind.rsplit(":", 1)
        if _p.isdigit():
            host = _h or host
            port = int(_p)
        else:
            app_path = bind
    else:
        app_path = bind

    typer.echo(f"Starting Buraq on http://{host}:{port}  [app: {app_path}]")

    try:
        from pathlib import Path

        from granian import Granian
        typer.echo("Server: granian (Rust ASGI)")
        Granian(
            app_path,
            address=host,
            port=port,
            interface="asgi",
            reload=reload,
            workers=workers if not reload else 1,
            working_dir=Path.cwd(),
        ).serve()
    except ImportError:
        import uvicorn
        typer.echo("Server: uvicorn (granian not installed)")
        uvicorn.run(
            app_path,
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            log_level="debug",
        )


# ─── Migrations ──────────────────────────────────────────────────────────────

@app.command()
def makemigrations(message: str = typer.Argument("auto", help="Migration message")):
    """Generate a new database migration (like Django's makemigrations)."""
    typer.echo(f"Creating migration: {message}")
    result = subprocess.run(["alembic", "revision", "--autogenerate", "-m", message])
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command()
def migrate(revision: str = typer.Argument("head", help="Target revision")):
    """Apply database migrations (like Django's migrate)."""
    typer.echo(f"Applying migrations to: {revision}")
    result = subprocess.run(["alembic", "upgrade", revision])
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command()
def rollback(steps: int = typer.Argument(1, help="Number of migrations to roll back")):
    """Roll back N migrations."""
    typer.echo(f"Rolling back {steps} migration(s)")
    subprocess.run(["alembic", "downgrade", f"-{steps}"])


@app.command()
def showmigrations():
    """List all migrations and their status."""
    subprocess.run(["alembic", "history", "--verbose"])


# ─── Auth ────────────────────────────────────────────────────────────────────

@app.command()
def createsuperuser(
    username: str = typer.Option(..., prompt=True),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
):
    """Create a superuser account."""
    import asyncio

    from buraq.contrib.auth.models import User
    from buraq.core.auth import hash_password
    from buraq.core.db import SessionLocal

    async def _create():
        async with SessionLocal() as db:
            user = User(
                username=username,
                email=email,
                hashed_password=hash_password(password),
                is_active=True,
                is_staff=True,
                is_superuser=True,
            )
            db.add(user)
            await db.commit()
            typer.echo(f"Superuser '{username}' created successfully.")

    asyncio.run(_create())


# ─── App Scaffolding ─────────────────────────────────────────────────────────

@app.command()
def startapp(name: str = typer.Argument(..., help="App name")):
    """Create a new Buraq app (like Django's startapp)."""
    base = Path(name)
    if base.exists():
        typer.echo(f"App '{name}' already exists.", err=True)
        raise typer.Exit(1)

    (base / "migrations").mkdir(parents=True)

    files = {
        "__init__.py": "",
        "models.py": (
            f"from buraq import models\n\n\n"
            f"class {name.title()}(models.Model):\n"
            f"    name = models.CharField(max_length=200)\n"
            f"    created_at = models.DateTimeField(auto_now_add=True)\n"
        ),
        "schemas.py": (
            "from pydantic import BaseModel\n\n\n"
            f"class {name.title()}Read(BaseModel):\n"
            "    id: int\n"
            "    name: str\n\n"
            "    model_config = {\"from_attributes\": True}\n\n\n"
            f"class {name.title()}Create(BaseModel):\n"
            "    name: str\n"
        ),
        "views.py": (
            f"from buraq.shortcuts import render, redirect, get_object_or_404\n"
            f"from .models import {name.title()}\n\n\n"
            f"async def list_{name}s(request):\n"
            f"    items = await {name.title()}.objects.all()\n"
            f"    return render(request, '{name}s/list.html', {{'{name}s': items}})\n\n\n"
            f"async def create_{name}(request):\n"
            f"    if request.method == 'POST':\n"
            f"        form = await request.form()\n"
            f"        await {name.title()}.objects.create(name=form.get('name'))\n"
            f"        return redirect('/{name}s/')\n"
            f"    return render(request, '{name}s/create.html')\n\n\n"
            f"async def get_{name}(request, pk: int):\n"
            f"    item = await get_object_or_404({name.title()}, id=pk)\n"
            f"    return render(request, '{name}s/detail.html', {{'{name}': item}})\n\n\n"
            f"async def update_{name}(request, pk: int):\n"
            f"    item = await get_object_or_404({name.title()}, id=pk)\n"
            f"    if request.method == 'POST':\n"
            f"        form = await request.form()\n"
            f"        await {name.title()}.objects.update(pk, name=form.get('name'))\n"
            f"        return redirect('/{name}s/')\n"
            f"    return render(request, '{name}s/edit.html', {{'{name}': item}})\n\n\n"
            f"async def delete_{name}(request, pk: int):\n"
            f"    await get_object_or_404({name.title()}, id=pk)\n"
            f"    await {name.title()}.objects.delete(pk)\n"
            f"    return redirect('/{name}s/')\n"
        ),
        "urls.py": (
            f"from buraq.urls import get, post, delete\n"
            f"from . import views\n\n\n"
            f"urlpatterns = [\n"
            f"    get('/',          views.list_{name}s,   name='{name}_list'),\n"
            f"    get('/new',       views.create_{name},  name='{name}_create'),\n"
            f"    post('/new',      views.create_{name},  name='{name}_create_post'),\n"
            f"    get('/<int:pk>',  views.get_{name},     name='{name}_detail'),\n"
            f"    get('/<int:pk>/edit',  views.update_{name},  name='{name}_update'),\n"
            f"    post('/<int:pk>/edit', views.update_{name},  name='{name}_update_post'),\n"
            f"    post('/<int:pk>/delete', views.delete_{name}, name='{name}_delete'),\n"
            f"]\n"
        ),
        "admin.py": (
            "from buraq.contrib.admin import ModelAdmin\n"
            f"from .models import {name.title()}\n\n\n"
            f"class {name.title()}Admin(ModelAdmin, model={name.title()}):\n"
            f"    column_list = [{name.title()}.id, {name.title()}.name]\n"
        ),
        "migrations/__init__.py": "",
    }

    for filename, content in files.items():
        (base / filename).write_text(content)

    typer.echo(f"App '{name}' created. Add '{name}' to INSTALLED_APPS in your settings.")


# ─── Static Files ────────────────────────────────────────────────────────────

@app.command()
def collectstatic(
    dest: str | None = typer.Option(None, help="Destination directory"),
    clear: bool = typer.Option(False, help="Clear destination before collecting"),
):
    """Collect all static files into STATIC_ROOT (like Django's collectstatic)."""
    from buraq.contrib.staticfiles import collect_static
    typer.echo("Collecting static files...")
    result = collect_static(dest_dir=dest, clear=clear)
    typer.echo(f"Done. Copied: {result['copied']}, Skipped: {result['skipped']}")


# ─── Cache ───────────────────────────────────────────────────────────────────

@app.command()
def clearcache():
    """Clear all cached data."""
    import asyncio

    from buraq.contrib.cache import cache

    async def _clear():
        await cache.clear()
        typer.echo("Cache cleared.")

    asyncio.run(_clear())


# ─── uv Package Manager ──────────────────────────────────────────────────────

def _uv() -> str:
    """Return the uv executable path, or raise if not installed."""
    uv_path = shutil.which("uv")
    if not uv_path:
        typer.echo(
            "uv is not installed. Install it with:\n"
            "  curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            "  or: pip install uv",
            err=True,
        )
        raise typer.Exit(1)
    return uv_path


@app.command()
def install(
    packages: list[str] = typer.Argument(..., help="Packages to install"),
    dev: bool = typer.Option(False, "--dev", "-d", help="Add as dev dependency"),
):
    """Install packages using uv (uv add)."""
    cmd = [_uv(), "add"]
    if dev:
        cmd.append("--dev")
    cmd.extend(packages)
    typer.echo(f"Installing: {', '.join(packages)}")
    subprocess.run(cmd)


@app.command()
def uninstall(packages: list[str] = typer.Argument(..., help="Packages to remove")):
    """Remove packages using uv (uv remove)."""
    cmd = [_uv(), "remove"] + list(packages)
    typer.echo(f"Removing: {', '.join(packages)}")
    subprocess.run(cmd)


@app.command()
def sync(
    all_extras: bool = typer.Option(False, "--all-extras", help="Include all optional deps"),
):
    """Sync all dependencies from pyproject.toml using uv."""
    cmd = [_uv(), "sync"]
    if all_extras:
        cmd.append("--all-extras")
    typer.echo("Syncing dependencies with uv...")
    subprocess.run(cmd)


@app.command("pip")
def pip_run(args: list[str] = typer.Argument(..., help="pip arguments")):
    """Run any uv pip command (e.g. buraq pip freeze)."""
    subprocess.run([_uv(), "pip"] + list(args))


@app.command()
def run(args: list[str] = typer.Argument(..., help="Command to run in uv environment")):
    """Run a command inside the uv virtual environment."""
    subprocess.run([_uv(), "run"] + list(args))


# ─── Project Scaffolding (startproject) ──────────────────────────────────────

@app.command()
def startproject(
    name: str = typer.Argument(..., help="Project name"),
    dest: str | None = typer.Option(None, help="Destination directory (defaults to ./<name>)"),
    use_postgres: bool = typer.Option(False, "--postgres", help="Configure for PostgreSQL"),
):
    """
    Scaffold a new Buraq project with uv, pyproject.toml, and full structure.
    Like Django's django-admin startproject.
    """
    project_dir = Path(dest or name)
    if project_dir.exists():
        typer.echo(f"Directory '{project_dir}' already exists.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Creating project '{name}' in {project_dir.resolve()}")

    # Create directories
    dirs = [
        project_dir / "config",
        project_dir / "templates",
        project_dir / "static" / "css",
        project_dir / "static" / "js",
        project_dir / "alembic" / "versions",
    ]
    for d in dirs:
        d.mkdir(parents=True)

    db_url = (
        f"postgresql+asyncpg://user:password@localhost:5432/{name}_db"
        if use_postgres
        else "sqlite+aiosqlite:///./db.sqlite3"
    )
    db_dep = '"asyncpg>=0.29.0"' if use_postgres else '"aiosqlite>=0.20.0"'

    # pyproject.toml — uv-native format
    (project_dir / "pyproject.toml").write_text(
        f'[project]\n'
        f'name = "{name}"\n'
        f'version = "0.1.0"\n'
        f'requires-python = ">=3.11"\n'
        f'dependencies = [\n'
        f'    "buraq>=0.1.0",\n'
        f'    {db_dep},\n'
        f']\n\n'
        f'# PEP 735 dependency groups — uv native dev deps\n'
        f'# Install with: uv sync --group dev\n'
        f'[dependency-groups]\n'
        f'dev = [\n'
        f'    "pytest>=8.0.0",\n'
        f'    "pytest-asyncio>=0.23.0",\n'
        f'    "httpx>=0.27.0",\n'
        f'    "ruff>=0.4.0",\n'
        f']\n\n'
        f'[tool.uv]\n'
        f'# uv manages the venv and lockfile for this project\n'
        f'managed = true\n'
        f'default-groups = ["dev"]\n\n'
        f'[tool.ruff]\n'
        f'line-length = 100\n'
        f'target-version = "py311"\n\n'
        f'[tool.pytest.ini_options]\n'
        f'asyncio_mode = "auto"\n'
        f'testpaths = ["tests"]\n'
    )

    # .env
    (project_dir / ".env").write_text(
        f"SECRET_KEY=change-me-in-production\n"
        f"DEBUG=True\n"
        f'DATABASE_URL={db_url}\n'
        f"ALLOWED_HOSTS=[\"localhost\", \"127.0.0.1\"]\n"
    )

    # .env.example
    (project_dir / ".env.example").write_text(
        (project_dir / ".env").read_text()
    )

    # .gitignore — uv.lock must NOT be ignored, it should be committed
    (project_dir / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.venv/\n.env\n*.sqlite3\n*.db\n"
        ".ruff_cache/\n.mypy_cache/\n.pytest_cache/\nalembic/versions/*.py\n"
        "!alembic/versions/.gitkeep\nstaticfiles/\nsent_emails/\n.cache/\nmedia/\n"
        "# uv.lock is intentionally NOT listed here — commit it to version control\n"
    )

    # alembic.ini
    (project_dir / "alembic.ini").write_text(
        "[alembic]\nscript_location = alembic\nprepend_sys_path = .\n"
        f"sqlalchemy.url = {db_url}\n\n"
        "[loggers]\nkeys = root,sqlalchemy,alembic\n\n"
        "[handlers]\nkeys = console\n\n"
        "[formatters]\nkeys = generic\n\n"
        "[logger_root]\nlevel = WARN\nhandlers = console\nqualname =\n\n"
        "[logger_sqlalchemy]\nlevel = WARN\nhandlers =\nqualname = sqlalchemy.engine\n\n"
        "[logger_alembic]\nlevel = INFO\nhandlers =\nqualname = alembic\n\n"
        "[handler_console]\nclass = StreamHandler\nargs = (sys.stderr,)\n"
        "level = NOTSET\nformatter = generic\n\n"
        "[formatter_generic]\nformat = %%(levelname)-5.5s [%%(name)s] %%(message)s\n"
        "datefmt = %%H:%%M:%%S\n"
    )

    # alembic/versions/.gitkeep
    (project_dir / "alembic" / "versions" / ".gitkeep").touch()

    # alembic/env.py
    (project_dir / "alembic" / "env.py").write_text(
        "import asyncio\n"
        "from logging.config import fileConfig\n"
        "from sqlalchemy import pool\n"
        "from sqlalchemy.engine import Connection\n"
        "from sqlalchemy.ext.asyncio import async_engine_from_config\n"
        "from alembic import context\n"
        "from buraq.core.db import Base\n\n"
        "# Import your models here so Alembic detects them:\n"
        "# from myapp.models import MyModel\n\n"
        "config = context.config\n"
        "if config.config_file_name is not None:\n"
        "    fileConfig(config.config_file_name)\n\n"
        "target_metadata = Base.metadata\n\n\n"
        "def do_run_migrations(connection: Connection) -> None:\n"
        "    context.configure(connection=connection, target_metadata=target_metadata)\n"
        "    with context.begin_transaction():\n"
        "        context.run_migrations()\n\n\n"
        "async def run_async_migrations() -> None:\n"
        "    from buraq.conf import settings\n"
        "    configuration = config.get_section(config.config_ini_section, {})\n"
        "    configuration['sqlalchemy.url'] = settings.DATABASE_URL\n"
        "    connectable = async_engine_from_config(\n"
        "        configuration, prefix='sqlalchemy.', poolclass=pool.NullPool\n"
        "    )\n"
        "    async with connectable.connect() as connection:\n"
        "        await connection.run_sync(do_run_migrations)\n"
        "    await connectable.dispose()\n\n\n"
        "def run_migrations_online() -> None:\n"
        "    asyncio.run(run_async_migrations())\n\n\n"
        "if context.is_offline_mode():\n"
        "    pass\n"
        "else:\n"
        "    run_migrations_online()\n"
    )

    # alembic/script.py.mako
    (project_dir / "alembic" / "script.py.mako").write_text(
        '"""${message}\n\nRevision ID: ${up_revision}\nRevises: ${down_revision | comma,n}\n'
        'Create Date: ${create_date}\n\n"""\nfrom typing import Sequence, Union\n'
        'from alembic import op\nimport sqlalchemy as sa\n${imports if imports else ""}\n\n'
        'revision: str = ${repr(up_revision)}\n'
        'down_revision: Union[str, None] = ${repr(down_revision)}\n'
        'branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}\n'
        'depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}\n\n\n'
        'def upgrade() -> None:\n    ${upgrades if upgrades else "pass"}\n\n\n'
        'def downgrade() -> None:\n    ${downgrades if downgrades else "pass"}\n'
    )

    # config/__init__.py
    (project_dir / "config" / "__init__.py").write_text("")

    # config/settings.py
    (project_dir / "config" / "settings.py").write_text(
        "from pathlib import Path\n\n"
        "BASE_DIR = Path(__file__).resolve().parent.parent\n\n"
        "SECRET_KEY = 'change-me-in-production'\n"
        "DEBUG = True\n"
        "ALLOWED_HOSTS = ['*']\n\n"
        "INSTALLED_APPS = [\n"
        "    'buraq.contrib.auth',\n"
        "]\n\n"
        f"DATABASE_URL = '{db_url}'\n\n"
        "TEMPLATES_DIR = str(BASE_DIR / 'templates')\n"
        "STATIC_DIR = str(BASE_DIR / 'static')\n\n"
        "# Email\n"
        "# EMAIL_BACKEND = 'buraq.contrib.email.backends.smtp.SMTPEmailBackend'\n"
        "# EMAIL_HOST = 'smtp.gmail.com'\n"
        "# EMAIL_PORT = 587\n\n"
        "# Cache\n"
        "# CACHE_BACKEND = 'buraq.contrib.cache.backends.redis.RedisCacheBackend'\n"
        "# CACHE_REDIS_URL = 'redis://localhost:6379/0'\n"
    )

    # config/urls.py
    (project_dir / "config" / "urls.py").write_text(
        "from buraq import Buraq\n"
        "from buraq.urls import path, include\n"
        "from buraq.contrib.admin import BuraqAdmin\n\n"
        "app = Buraq(settings_module='config.settings')\n"
        "admin = BuraqAdmin(app)\n\n\n"
        "# ── URL Configuration (like Django's urls.py) ──────────────────────\n"
        "# Add your apps here after running: python manage.py startapp <name>\n"
        "urlpatterns = [\n"
        "    path('/auth', include('buraq.contrib.auth.urls')),\n"
        "    # path('/posts', include('posts.urls')),\n"
        "]\n\n"
        "app.load_urls(urlpatterns)\n\n\n"
        "@app.get('/')\n"
        "async def index():\n"
        f"    return {{\"message\": \"Welcome to {name}!\", \"docs\": \"/api/docs\"}}\n"
    )

    # manage.py — auto-detects .venv so `python manage.py` just works
    (project_dir / "manage.py").write_text(
        '#!/usr/bin/env python\n'
        '"""Run like Django: python manage.py <command>"""\n'
        'import os, sys\n'
        'from pathlib import Path\n\n'
        'def _bootstrap():\n'
        '    root = Path(__file__).parent.resolve()\n'
        '    venv = root / ".venv"\n'
        '    python = venv / "Scripts" / "python.exe"\n'
        '    if not python.exists():\n'
        '        python = venv / "bin" / "python"\n'
        '    if python.exists() and Path(sys.executable).resolve() != python.resolve():\n'
        '        os.execv(str(python), [str(python)] + sys.argv)\n\n'
        '_bootstrap()\n\n'
        'sys.path.insert(0, str(Path(__file__).parent))\n'
        'from buraq.management.cli import app\n\n'
        'if __name__ == "__main__":\n'
        '    app()\n'
    )

    # templates/base.html
    (project_dir / "templates" / "base.html").write_text(
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>{% block title %}" + name.title() + "{% endblock %}</title>\n"
        "</head>\n<body>\n"
        "{% block content %}{% endblock %}\n"
        "</body>\n</html>\n"
    )

    typer.echo("\nProject structure created. Now run:")
    typer.echo(f"\n  cd {project_dir}")
    typer.echo("  uv sync                        # install dependencies")
    typer.echo("  python manage.py migrate       # create tables")
    typer.echo("  python manage.py runserver     # start server")
    typer.echo("\nAPI docs will be at: http://127.0.0.1:8000/api/docs\n")

    # Auto-run uv sync if uv is available
    uv = shutil.which("uv")
    if uv and typer.confirm("Run 'uv sync' now to install dependencies?", default=True):
        subprocess.run([uv, "sync"], cwd=project_dir)


# ─── Custom Management Commands ──────────────────────────────────────────────

@app.command("manage")
def run_command(
    command: str = typer.Argument(..., help="Custom management command name"),
    args: list[str] | None = typer.Argument(None, help="Command arguments"),
):
    """
    Run a custom management command defined in any installed app.

    Commands live at: <app>/management/commands/<command>.py

    Example:
        python manage.py manage send_reminders --days=14
    """
    import importlib

    from buraq.conf import settings

    for app_name in settings.INSTALLED_APPS:
        try:
            mod = importlib.import_module(f"{app_name}.management.commands.{command}")
            if not hasattr(mod, "Command"):
                typer.echo(f"Module {app_name}.management.commands.{command} has no Command class.", err=True)
                continue
            cmd = mod.Command()
            parser = cmd.create_parser("manage.py", command)
            options = vars(parser.parse_args(args or []))
            cmd.execute(**options)
            return
        except ModuleNotFoundError:
            continue

    typer.echo(f"Unknown management command: '{command}'. No app provides it.", err=True)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
