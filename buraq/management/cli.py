import os
import shutil
import subprocess
import sys
from pathlib import Path

import typer

# Discovery lives in buraq.conf so alembic's env.py and any other entry point
# resolve the settings module exactly the way the CLI does.
from buraq.conf import discover_settings_module as _discover_settings_module


def _load_apps() -> None:
    """
    Load INSTALLED_APPS from sync CLI code.

    A model class reaches the ORM registry only when its module is imported, so
    a command reading model metadata sees nothing unless something imported the
    apps first -- `dumpdata` emitted `{}` for a fully populated database, and
    `sqlflush` printed no statements at all, for exactly this reason.
    """
    import asyncio

    async def _run() -> None:
        from buraq.apps import setup
        from buraq.core.db import _lazy

        await setup()
        # A ready() hook may have opened a connection, and it belongs to the
        # loop that is about to close.
        if _lazy._engine is not None:
            await _lazy._engine.dispose()

    asyncio.run(_run())


def _fire_signal(name: str, **kwargs) -> None:
    """
    Send a Buraq signal from sync CLI code.

    ``Signal.send`` is a coroutine and the CLI has no running loop, so this owns
    one for the duration of the send. Loading the app configs, the receivers
    themselves and the ORM they query all have to share that single loop, so
    they happen together inside it.
    """
    import asyncio
    import logging

    from buraq import signals as _signals

    sig = getattr(_signals, name, None)
    if sig is None:
        return

    async def _send() -> None:
        from buraq.apps import setup as _setup_apps
        from buraq.core.db import _lazy

        await _setup_apps()  # ready() is what connects the receivers
        try:
            await sig.send(sender=None, **kwargs)
        finally:
            # Receivers open connections bound to this loop, which dies with
            # asyncio.run() below -- hand them back before that happens.
            if _lazy._engine is not None:
                await _lazy._engine.dispose()

    try:
        asyncio.run(_send())
    except Exception:
        # A receiver failing must not make a completed migration look failed,
        # but it must not vanish either -- this used to be `except: pass`, which
        # is how the signal stayed broken.
        logging.getLogger("buraq.signals").exception(
            "Error sending %r (the migration itself was applied)", name
        )

app = typer.Typer(
    name="buraq",
    help="Buraq management CLI — run servers, migrations, and project commands.",
    add_completion=False,
)


# ─── Global options ───────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def _cli(
    ctx: typer.Context,
    settings_module: str = typer.Option(
        None,
        "--settings",
        help=(
            "Dotted Python path to the settings module "
            "(e.g. config.prod_settings). "
            "Also read from the BURAQ_SETTINGS_MODULE environment variable."
        ),
        envvar="BURAQ_SETTINGS_MODULE",
    ),
):
    """Buraq management CLI — run servers, migrations, and project commands."""
    if not settings_module:
        settings_module = _discover_settings_module()

    if settings_module:
        import sys

        cwd = str(Path.cwd())
        if cwd not in sys.path:
            sys.path.insert(0, cwd)

        import importlib
        try:
            module = importlib.import_module(settings_module)
        except ImportError as exc:
            typer.echo(
                f"Error: cannot import settings module {settings_module!r}: {exc}",
                err=True,
            )
            raise typer.Exit(1) from exc

        from buraq.conf import settings as _settings
        for key, val in vars(module).items():
            if key.isupper() and not key.startswith("_") and hasattr(_settings, key):
                setattr(_settings, key, val)

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


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
    server: str = typer.Option(
        "auto",
        envvar="BURAQ_SERVER",
        help=(
            "ASGI server: 'auto' (granian, falling back to uvicorn), 'granian', or "
            "'uvicorn'. Also read from BURAQ_SERVER, so a machine where granian "
            "does not run can set it once."
        ),
    ),
):
    """Start the development server."""
    app_path = "main:app"

    # Supports: runserver 8001  OR  runserver 0.0.0.0:8001  OR  runserver main:app
    if bind.isdigit():
        port = int(bind)
    elif ":" in bind:
        _h, _p = bind.rsplit(":", 1)
        if _p.isdigit():
            # host:port — e.g. 0.0.0.0:8001 or 127.0.0.1:8080
            host = _h or host
            port = int(_p)
        else:
            # module:attr — e.g. main:app or config.urls:app
            app_path = bind
    else:
        app_path = bind

    typer.echo(f"Starting Buraq on http://{host}:{port}  [app: {app_path}]")

    def _serve_uvicorn(reason: str = "") -> None:
        from pathlib import Path

        import uvicorn

        typer.echo(f"Server: uvicorn{f' ({reason})' if reason else ''}")
        uvicorn.run(
            app_path,
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            # The reloader runs the app in a subprocess that does not inherit the
            # working directory on sys.path, so "main:app" would not import.
            # granian gets the same treatment through working_dir.
            app_dir=str(Path.cwd()),
            log_level="debug",
        )

    def _serve_granian() -> bool:
        """
        Run granian. Returns True if it ever accepted a connection.

        Elapsed time is not a usable health signal: granian retries a failing
        worker for a while before giving up, so a broken server can still run
        for many seconds. Probing the port answers the actual question — did
        anything ever get served?
        """
        import socket
        import threading
        import time
        from pathlib import Path

        from granian import Granian

        served = threading.Event()
        probe_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host

        def _probe() -> None:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not served.is_set():
                try:
                    with socket.create_connection((probe_host, port), timeout=0.5):
                        served.set()
                        return
                except OSError:
                    time.sleep(0.25)
            if not served.is_set():
                # granian keeps retrying a dead worker for a while before giving
                # up, so say something now rather than leaving the user watching
                # a server that is never going to accept a request.
                typer.secho(
                    f"\ngranian is not accepting connections on "
                    f"{probe_host}:{port} — its worker failed to start.\n"
                    f"Restart with:  buraq runserver --server uvicorn\n",
                    fg="yellow",
                )

        threading.Thread(target=_probe, daemon=True).start()

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
        return served.is_set()

    if server == "uvicorn":
        _serve_uvicorn()
        return

    try:
        served = _serve_granian()
    except ImportError:
        if server == "granian":
            typer.secho("granian is not installed. Install it, or use --server uvicorn.", fg="red")
            raise typer.Exit(1) from None
        _serve_uvicorn("granian not installed")
        return

    # granian imports fine but its worker can die on start — a Rust extension that
    # does not match the platform still imports cleanly. If nothing was ever served,
    # fall back rather than exiting silently and leaving the user with no server.
    if not served:
        if server == "granian":
            typer.secho(
                "granian exited immediately — its worker failed to start. "
                "Retry with --server uvicorn to confirm your app is fine.",
                fg="red",
            )
            raise typer.Exit(1)
        typer.secho(
            "granian exited immediately (its worker failed to start); falling back to uvicorn.",
            fg="yellow",
        )
        _serve_uvicorn("granian worker failed")


# ─── Migrations ──────────────────────────────────────────────────────────────


def _install_dependencies(project_dir: Path) -> bool:
    """
    Install the new project's dependencies. True when it is ready to run.

    Creating the files and installing into them are separate kinds of work with
    separate failure modes -- no network, a blocked index, a mirror that is down.
    None of those make the scaffold wrong, so a failure here is reported and the
    caller carries on rather than leaving a half-made project behind.
    """
    uv = shutil.which("uv")
    if uv:
        typer.echo("Installing dependencies with uv...")
        return subprocess.run([uv, "sync"], cwd=project_dir).returncode == 0

    typer.echo("Creating .venv and installing dependencies with pip...")
    venv_dir = project_dir / ".venv"
    if subprocess.run([sys.executable, "-m", "venv", str(venv_dir)]).returncode != 0:
        return False

    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    pip = bin_dir / ("pip.exe" if os.name == "nt" else "pip")
    return subprocess.run([str(pip), "install", "buraq"], cwd=project_dir).returncode == 0


def _scaffold_version_locations(apps: list[str] | None = None) -> str:
    """
    The `version_locations` line for a new project's alembic.ini.

    The project's own directory comes first, then one entry per installed Buraq
    app that ships migrations.
    """
    locations = ["%(here)s/alembic/versions"]
    for app in apps if apps is not None else ["buraq.contrib.auth"]:
        locations.append(f"{app}:migrations/versions")
    return "\n".join(f"    {loc}" for loc in locations)


def _require_alembic() -> None:
    """
    Fail with something actionable when the project has no Alembic setup.

    Alembic's own message for this is "No 'script_location' key found in
    configuration", which does not tell you that the file is simply missing.
    Projects created by `buraq startproject` are scaffolded with it; older or
    hand-made projects may not be.
    """
    if Path("alembic.ini").exists():
        return

    typer.secho("No alembic.ini found in this directory.", fg="red")
    typer.echo(
        "Migrations need an Alembic setup: alembic.ini plus an alembic/ directory.\n"
        "`buraq startproject` scaffolds both. To add them to an existing project, "
        "run `alembic init alembic`, then point alembic/env.py at "
        "buraq.core.db:Base metadata."
    )
    raise typer.Exit(1)


def _script_directory():
    """This project's Alembic ScriptDirectory, or None if it cannot be read."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        return ScriptDirectory.from_config(Config("alembic.ini"))
    except Exception:
        return None


def _versions_dir() -> Path | None:
    """
    The project's own versions directory.

    Installed Buraq apps contribute version locations inside the package, so the
    project's directory is the one under the working directory. Picking the
    wrong one wrote a project's migration into site-packages.
    """
    script = _script_directory()
    if script is None:
        return None

    cwd = Path.cwd().resolve()
    for location in script.version_locations:
        path = Path(location).resolve()
        if path == cwd or cwd in path.parents:
            return path
    return Path(script.dir) / "versions"


def _project_revision_args(versions: Path | None) -> list[str]:
    """
    Pin a new revision to the project's own directory and branch.

    With more than one version location Alembic picks a directory on its own,
    and it chose the installed package. It equally needs telling which head to
    follow, since the framework's branches are heads too.
    """
    if versions is None:
        return []

    args = ["--version-path", str(versions)]
    script = _script_directory()
    if script is None:
        return args

    own = [rev for rev in script.walk_revisions() if Path(rev.path).parent.resolve() == versions]
    if not own:
        # First migration here: start a branch rather than extending one of the
        # framework's.
        return [*args, "--head", "base", "--branch-label", "project"]

    heads = [rev.revision for rev in own if rev.is_head] or [own[0].revision]
    return [*args, "--head", heads[0]]


def _is_empty_migration(path: Path) -> bool:
    """True when the revision's upgrade() does nothing -- i.e. no schema drift."""
    import ast

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
            body = [
                stmt
                for stmt in node.body
                # Drop the docstring; comments are absent from the AST already.
                if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
            ]
            return all(isinstance(stmt, ast.Pass) for stmt in body)
    return False


def _names_an_installed_app(text: str) -> bool:
    """Does `text` look like one of INSTALLED_APPS rather than a description?"""
    from buraq.conf import settings

    labels = set()
    for entry in getattr(settings, "INSTALLED_APPS", None) or []:
        parts = entry.split(".")
        labels.update({entry, parts[0], parts[-1]})
    return text in labels


@app.command()
def makemigrations(
    message: str = typer.Argument(
        "auto",
        help="Description of the change, e.g. 'add slug to post'. Not an app name.",
    ),
):
    """
    Generate a new database migration.

    The argument is the migration's description, which becomes part of the
    revision filename. Buraq keeps one migration history for the whole project,
    so there is no app to scope a run to -- every model change is included.
    """
    _require_alembic()

    if _names_an_installed_app(message):
        typer.secho(
            f"Note: {message!r} is being used as the migration's description, not "
            "as an app to migrate. Buraq migrates the whole project at once.",
            fg="yellow",
        )

    typer.echo(f"Creating migration: {message}")

    versions = _versions_dir()
    before = set(versions.glob("*.py")) if versions and versions.is_dir() else set()

    result = subprocess.run(
        [
            sys.executable, "-m", "alembic", "revision", "--autogenerate",
            "-m", message, *_project_revision_args(versions),
        ],
        capture_output=True,
        text=True,
        # Alembic emits paths and model names; decoding those with whatever the
        # locale happens to be fails outright under the POSIX locale that minimal
        # container images default to.
        encoding="utf-8",
        errors="replace",
    )
    if result.stderr:
        typer.echo(result.stderr, nl=False, err=True)

    if result.returncode != 0:
        if "not up to date" in result.stderr:
            # Alembic will not diff against a database that is behind its own
            # history, because the pending revisions would be generated twice.
            typer.echo("")
            typer.secho(
                "The database is behind the migrations already on disk. "
                "Run `buraq migrate` first, then makemigrations again.",
                fg="yellow",
            )
        raise typer.Exit(result.returncode)

    # Autogenerate always writes a file, even when it found nothing to put in
    # it. Left behind, empty revisions pile up in the history indistinguishable
    # from real ones -- so drop it and say plainly that nothing changed.
    new_files = (set(versions.glob("*.py")) - before) if versions and versions.is_dir() else set()
    empty = [path for path in new_files if _is_empty_migration(path)]
    for path in empty:
        path.unlink()

    if empty:
        # Suppress alembic's "Generating ... done" for a file that no longer exists.
        typer.secho("No changes detected - no migration created.", fg="green")
    elif result.stdout:
        typer.echo(result.stdout, nl=False)


@app.command()
def migrate(
    revision: str = typer.Argument(
        "heads", help="Target revision ('heads' applies every branch)"
    ),
):
    """
    Apply database migrations.

    Defaults to ``heads`` rather than ``head`` because installed Buraq apps ship
    their own migrations on their own branches; ``head`` fails outright when more
    than one branch exists.
    """
    _require_alembic()
    typer.echo(f"Applying migrations to: {revision}")
    _fire_signal("pre_migrate", revision=revision, verbosity=1)
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision])
    if result.returncode != 0:
        raise typer.Exit(result.returncode)
    _fire_signal("post_migrate", revision=revision, verbosity=1)


@app.command()
def rollback(steps: int = typer.Argument(1, help="Number of migrations to roll back")):
    """Roll back N migrations."""
    _require_alembic()
    typer.echo(f"Rolling back {steps} migration(s)")
    _fire_signal("pre_migrate", revision=f"-{steps}", verbosity=1)
    result = subprocess.run([sys.executable, "-m", "alembic", "downgrade", f"-{steps}"])
    if result.returncode != 0:
        raise typer.Exit(result.returncode)
    _fire_signal("post_migrate", revision=f"-{steps}", verbosity=1)


@app.command()
def showmigrations():
    """List all migrations and their status."""
    _require_alembic()
    result = subprocess.run([sys.executable, "-m", "alembic", "history", "--verbose"])
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


# ─── Auth ────────────────────────────────────────────────────────────────────

@app.command()
def createsuperuser(
    username: str = typer.Option(None, help="Username for the new superuser"),
    email: str = typer.Option(None, help="Email address"),
    password: str = typer.Option(None, help="Password (prompted if omitted)", hide_input=True),
    no_input: bool = typer.Option(
        False, "--no-input", help="Read all values from options, skip prompts"
    ),
):
    """Create a superuser account for the admin panel."""
    _load_apps()
    import asyncio
    import getpass

    if not no_input:
        if not username:
            username = typer.prompt("Username")
        if not email:
            email = typer.prompt("Email address")
        if not password:
            while True:
                pw1 = getpass.getpass("Password: ")
                if not pw1:
                    typer.echo("Password cannot be empty.", err=True)
                    continue
                pw2 = getpass.getpass("Password (again): ")
                if pw1 != pw2:
                    typer.echo("Passwords do not match. Please try again.", err=True)
                    continue
                password = pw1
                break
    else:
        if not username or not email or not password:
            typer.echo("--no-input requires --username, --email, and --password.", err=True)
            raise typer.Exit(1)

    from buraq.contrib.auth import make_password
    from buraq.contrib.auth.models import User

    async def _create():
        if await User.objects.get_or_none(username=username) is not None:
            typer.echo(f"Error: a user with username '{username}' already exists.", err=True)
            raise typer.Exit(1)

        if await User.objects.get_or_none(email=email) is not None:
            typer.echo(f"Error: a user with email '{email}' already exists.", err=True)
            raise typer.Exit(1)

        await User.objects.create(
            username=username,
            email=email,
            hashed_password=await make_password(password),
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        typer.echo(
            typer.style(f"Superuser '{username}' created successfully.", fg=typer.colors.GREEN)
        )

    asyncio.run(_create())


# ─── App Scaffolding ─────────────────────────────────────────────────────────

@app.command()
def startapp(name: str = typer.Argument(..., help="App name")):
    """Create a new Buraq app with the standard directory structure."""
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
            f"    return await render(request, '{name}s/list.html', {{'{name}s': items}})\n\n\n"
            f"async def create_{name}(request):\n"
            f"    if request.method == 'POST':\n"
            f"        form = await request.form()\n"
            f"        await {name.title()}.objects.create(name=form.get('name'))\n"
            f"        return redirect('/{name}s/')\n"
            f"    return await render(request, '{name}s/create.html')\n\n\n"
            f"async def get_{name}(request, pk: int):\n"
            f"    item = await get_object_or_404({name.title()}, id=pk)\n"
            f"    return await render(request, '{name}s/detail.html', {{'{name}': item}})\n\n\n"
            f"async def update_{name}(request, pk: int):\n"
            f"    item = await get_object_or_404({name.title()}, id=pk)\n"
            f"    if request.method == 'POST':\n"
            f"        form = await request.form()\n"
            f"        await {name.title()}.objects.update(pk, name=form.get('name'))\n"
            f"        return redirect('/{name}s/')\n"
            f"    return await render(request, '{name}s/edit.html', {{'{name}': item}})\n\n\n"
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
            "from buraq.contrib.admin import ModelAdmin, site\n"
            f"from .models import {name.title()}\n\n\n"
            f"class {name.title()}Admin(ModelAdmin):\n"
            f"    list_display = [\"id\", \"name\"]\n\n\n"
            f"site.register({name.title()}, {name.title()}Admin)\n"
        ),
        "migrations/__init__.py": "",
    }

    for filename, content in files.items():
        (base / filename).write_text(content, encoding="utf-8")

    typer.echo(f"App '{name}' created. Add '{name}' to INSTALLED_APPS in your settings.")


# ─── Static Files ────────────────────────────────────────────────────────────

@app.command()
def collectstatic(
    dest: str | None = typer.Option(None, help="Destination directory (overrides STATIC_ROOT)"),
    clear: bool = typer.Option(False, help="Clear destination before collecting"),
):
    """Collect all static files into STATIC_ROOT using configured finders and storage."""
    from buraq.contrib.staticfiles import collect_static
    from buraq.contrib.staticfiles.storage import get_storage
    storage = get_storage()
    location = dest or storage.location
    typer.echo(f"Collecting static files into {location} ...")
    result = collect_static(dest_dir=dest, clear=clear)
    typer.echo(
        f"Done. Copied: {result['copied']}, "
        f"Skipped (unchanged): {result['skipped']}, "
        f"Post-processed: {result['post_processed']}"
    )


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


# ─── Internationalization ─────────────────────────────────────────────────────

@app.command()
def makemessages(
    locale: list[str] = typer.Option(..., "--locale", "-l", help="Locale(s) to generate"),
    domain: str = typer.Option("messages", "--domain", "-d", help="Message domain"),
    extensions: list[str] = typer.Option(["py", "html"], "--extension", "-e", help="Extensions"),
    ignore: list[str] = typer.Option([], "--ignore", "-i", help="Paths to ignore"),
):
    """
    Extract translatable strings into .po files.

    Example:
        buraq makemessages -l ar
        buraq makemessages -l ar -l fr -l es
    """
    try:
        import babel.messages  # noqa: F401
    except ImportError:
        typer.echo("Error: Babel is required. Run: buraq install babel", err=True)
        raise typer.Exit(1) from None

    cwd = Path.cwd()
    ignore_list = list(ignore) + [".venv", "site", "dist", "__pycache__"]

    for lang in locale:
        po_path = cwd / "locale" / lang / "LC_MESSAGES" / f"{domain}.po"
        po_path.parent.mkdir(parents=True, exist_ok=True)

        pot_path = cwd / "locale" / f"{domain}.pot"

        typer.echo(f"Extracting messages for locale '{lang}'...")

        extract_args = [
            "pybabel", "extract",
            "--input-dirs", str(cwd),
            "--output", str(pot_path),
            "--project", "buraq",
        ]
        for ign in ignore_list:
            extract_args += ["--ignore-dirs", ign]

        result = subprocess.run(extract_args, capture_output=True, text=True)
        if result.returncode != 0:
            typer.echo(result.stderr, err=True)
            raise typer.Exit(1)

        if po_path.exists():
            update_args = [
                "pybabel", "update", "-i", str(pot_path),
                "-d", str(cwd / "locale"), "-l", lang,
            ]
            result = subprocess.run(update_args, capture_output=True, text=True)
        else:
            init_args = [
                "pybabel", "init", "-i", str(pot_path),
                "-d", str(cwd / "locale"), "-l", lang,
            ]
            result = subprocess.run(init_args, capture_output=True, text=True)

        if result.returncode != 0:
            typer.echo(result.stderr, err=True)
            raise typer.Exit(1)

        typer.echo(f"  Done → locale/{lang}/LC_MESSAGES/{domain}.po")

    typer.echo("makemessages complete. Translate the .po files then run: buraq compilemessages")


@app.command()
def compilemessages(
    domain: str = typer.Option("messages", "--domain", "-d", help="Message domain"),
):
    """
    Compile .po translation files into binary .mo files.

    Example:
        buraq compilemessages
    """
    try:
        import subprocess as _sp
        _sp.run(["pybabel", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, Exception):  # noqa: BLE001
        typer.echo("Error: Babel is required. Run: buraq install babel", err=True)
        raise typer.Exit(1) from None

    locale_dir = Path.cwd() / "locale"
    if not locale_dir.exists():
        typer.echo("No locale/ directory found. Run buraq makemessages first.", err=True)
        raise typer.Exit(1)

    result = subprocess.run(
        ["pybabel", "compile", "-d", str(locale_dir), "--domain", domain],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        typer.echo(result.stderr, err=True)
        raise typer.Exit(1)

    typer.echo(result.stdout or "compilemessages complete. .mo files updated.")

    from buraq.utils.translation import invalidate_cache
    invalidate_cache()


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
    directory: str | None = typer.Argument(
        None, help="Where to put it (defaults to ./<name>)"
    ),
    dest: str | None = typer.Option(
        None, help="Same as the directory argument, kept for existing scripts"
    ),
    use_postgres: bool = typer.Option(False, "--postgres", help="Configure for PostgreSQL"),
    no_install: bool = typer.Option(
        False, "--no-install", help="Only write the files; do not install dependencies"
    ),
):
    """
    Scaffold a new Buraq project: pyproject.toml, settings, migrations, templates.

    The target directory is the second argument, the way `cp`, `mv` and
    `git clone` take theirs:

        buraq startproject myblog
        buraq startproject myblog blog_folder

    Files land directly in that directory -- no extra folder is nested inside it.
    """
    if directory and dest and directory != dest:
        typer.secho(
            f"Two different directories given: {directory!r} and --dest {dest!r}. "
            "Pass one.",
            fg="red",
        )
        raise typer.Exit(2)

    project_dir = Path(directory or dest or name)
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
    , encoding="utf-8")

    # Generate a random secret key for this project
    import secrets as _secrets
    _secret_key = _secrets.token_hex(50)

    # .env
    (project_dir / ".env").write_text(
        f"SECRET_KEY={_secret_key}\n"
        f"DEBUG=True\n"
        f'DATABASE_URL={db_url}\n'
        f"ALLOWED_HOSTS=[\"localhost\", \"127.0.0.1\"]\n"
    , encoding="utf-8")

    # .env.example — use a placeholder so the real key is never committed
    (project_dir / ".env.example").write_text(
        f"SECRET_KEY=<generate-with: python -c \"import secrets; print(secrets.token_hex(50))\">\n"
        f"DEBUG=False\n"
        f'DATABASE_URL={db_url}\n'
        f"ALLOWED_HOSTS=[\"yourdomain.com\"]\n"
    , encoding="utf-8")

    # .gitignore — uv.lock must NOT be ignored, it should be committed
    (project_dir / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.venv/\n.env\n*.sqlite3\n*.db\n"
        ".ruff_cache/\n.mypy_cache/\n.pytest_cache/\nalembic/versions/*.py\n"
        "!alembic/versions/.gitkeep\nstaticfiles/\nsent_emails/\n.cache/\nmedia/\n"
        "# uv.lock is intentionally NOT listed here — commit it to version control\n"
    , encoding="utf-8")

    # alembic.ini
    (project_dir / "alembic.ini").write_text(
        "[alembic]\nscript_location = alembic\nprepend_sys_path = .\n"
        # Buraq's contrib apps ship their own migrations; alembic resolves
        # package:path against the installed package, so nothing is copied in.
        # One path per line: path_separator = os would make this file mean
        # different things on Windows and Linux, and newline survives paths
        # that contain spaces.
        "path_separator = newline\n"
        f"version_locations =\n{_scaffold_version_locations()}\n\n"
        f"sqlalchemy.url = {db_url}\n\n"
        "[loggers]\nkeys = root,sqlalchemy,alembic,alembic_plugins\n\n"
        "[handlers]\nkeys = console\n\n"
        "[formatters]\nkeys = generic\n\n"
        "[logger_root]\nlevel = WARN\nhandlers = console\nqualname =\n\n"
        "[logger_sqlalchemy]\nlevel = WARN\nhandlers =\nqualname = sqlalchemy.engine\n\n"
        "[logger_alembic]\nlevel = INFO\nhandlers =\nqualname = alembic\n\n"
        # Plugin setup is announced on every autogenerate run and says
        # nothing about the migration itself.
        "[logger_alembic_plugins]\nlevel = WARN\nhandlers =\n"
        "qualname = alembic.runtime.plugins\n\n"
        "[handler_console]\nclass = StreamHandler\nargs = (sys.stderr,)\n"
        "level = NOTSET\nformatter = generic\n\n"
        "[formatter_generic]\nformat = %(levelname)-5.5s [%(name)s] %(message)s\n"
        "datefmt = %H:%M:%S\n"
    , encoding="utf-8")

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
        "from buraq.apps import configure\n"
        "\n"
        "# Loads settings and imports every app's models, so Base.metadata reflects\n"
        "# INSTALLED_APPS. Without it autogenerate sees no tables and a new project\n"
        "# can never generate its first migration.\n"
        "configure()\n"
        "config = context.config\n"
        "if config.config_file_name is not None:\n"
        "    fileConfig(config.config_file_name)\n\n"
        "target_metadata = Base.metadata\n\n\n"
        "def include_object(obj, name, type_, reflected, compare_to):\n"
        "    from buraq.core.db import tables_migrations_ignore\n\n"
        "    if type_ == 'table' and name in tables_migrations_ignore():\n"
        "        return False\n"
        "    return True\n\n\n"
        "def do_run_migrations(connection: Connection) -> None:\n"
        "    context.configure(\n"
        "        connection=connection,\n"
        "        target_metadata=target_metadata,\n"
        "        include_object=include_object,\n"
        "    )\n"
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
    , encoding="utf-8")

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
    , encoding="utf-8")

    # config/__init__.py
    (project_dir / "config" / "__init__.py").write_text("", encoding="utf-8")

    # config/settings.py
    (project_dir / "config" / "settings.py").write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "BASE_DIR = Path(__file__).resolve().parent.parent\n\n"
        "# Load from .env — never hardcode these values\n"
        "SECRET_KEY = os.environ.get('SECRET_KEY', '')\n"
        "DEBUG = os.environ.get('DEBUG', 'False') == 'True'\n"
        "ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')\n\n"
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
    , encoding="utf-8")

    # config/urls.py
    (project_dir / "config" / "urls.py").write_text(
        "from buraq import Buraq\n"
        "from buraq.urls import path, include\n"
        "from buraq.contrib.admin import BuraqAdmin\n\n"
        "app = Buraq(settings_module='config.settings')\n"
        "admin = BuraqAdmin(app)\n\n\n"
        "# ── URL Configuration ───────────────────────────────────────────────\n"
        "# Add your apps here after running: python manage.py startapp <name>\n"
        "urlpatterns = [\n"
        "    path('/auth', include('buraq.contrib.auth.urls')),\n"
        "    # path('/posts', include('posts.urls')),\n"
        "]\n\n"
        "app.load_urls(urlpatterns)\n\n\n"
        "@app.get('/')\n"
        "async def index():\n"
        f"    return {{\"message\": \"Welcome to {name}!\", \"docs\": \"/api/docs\"}}\n"
    , encoding="utf-8")

    # main.py — entry point so `main:app` (the runserver default) resolves correctly
    (project_dir / "main.py").write_text(
        "# Entry point — exposes `app` at the module level so `buraq runserver` works.\n"
        "from config.urls import app  # noqa: F401\n"
    , encoding="utf-8")

    # manage.py — auto-detects .venv so `python manage.py` just works
    (project_dir / "manage.py").write_text(
        '#!/usr/bin/env python\n'
        '"""Run: python manage.py <command>"""\n'
        'import os, sys\n'
        'from pathlib import Path\n\n'
        'def _bootstrap():\n'
        '    root = Path(__file__).parent.resolve()\n'
        '    venv = root / ".venv"\n'
        '    python = venv / "Scripts" / "python.exe"\n'
        '    if not python.exists():\n'
        '        python = venv / "bin" / "python"\n'
        '    if not python.exists() or Path(sys.executable).resolve() == python.resolve():\n'
        '        return\n'
        '    argv = [str(python)] + sys.argv\n'
        '    if os.name == \"nt\":\n'
        '        # Windows has no real exec: execv() spawns a child and exits this\n'
        '        # process, so the shell takes its prompt back while the server runs\n'
        '        # on detached and Ctrl+C reaches nobody.\n'
        '        import subprocess\n'
        '        raise SystemExit(subprocess.run(argv).returncode)\n'
        '    os.execv(str(python), argv)\n\n'
        '_bootstrap()\n\n'
        'sys.path.insert(0, str(Path(__file__).parent))\n'
        'os.environ.setdefault(\"BURAQ_SETTINGS_MODULE\", \"config.settings\")\n'
        'from buraq.management.cli import app\n\n'
        'if __name__ == "__main__":\n'
        '    app()\n'
    , encoding="utf-8")

    # templates/base.html
    (project_dir / "templates" / "base.html").write_text(
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>{% block title %}" + name.title() + "{% endblock %}</title>\n"
        "</head>\n<body>\n"
        "{% block content %}{% endblock %}\n"
        "</body>\n</html>\n"
    , encoding="utf-8")

    typer.echo("")
    ready = False if no_install else _install_dependencies(project_dir)

    typer.echo("\nProject created. Now run:")
    typer.echo(f"\n  cd {project_dir}")
    if not ready:
        # Either --no-install, or the install did not finish. Either way the
        # files are correct and this is the step that is still outstanding.
        if shutil.which("uv"):
            typer.echo("  uv sync                        # install dependencies")
        else:
            typer.echo("  python -m venv .venv           # create the environment")
            typer.echo("  pip install buraq              # install dependencies")
    typer.echo("  buraq migrate                  # create tables")
    typer.echo("  buraq runserver                # start server")
    typer.echo("\nAPI docs will be at: http://127.0.0.1:8000/api/docs\n")

    # No prompt to run the install for you: it duplicates the step printed above,
    # and reading a confirmation from a closed stdin aborted with exit 1 on a
    # project that had in fact been created -- breaking `startproject x && cd x`
    # in scripts and CI.


# ─── URL Listing ─────────────────────────────────────────────────────────────

@app.command()
def listurls(
    app_path: str = typer.Option(
        "main:app",
        "--app",
        help="ASGI app to inspect, e.g. 'main:app' or 'config.urls:app'",
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable coloured output"),
):
    """
    List all registered URL routes and their HTTP methods.

    Named routes (registered with name=) also show their name.

    Example:
        python manage.py listurls
        python manage.py listurls --app config.urls:app
    """
    import importlib

    try:
        module_path, obj_name = app_path.rsplit(":", 1)
        module = importlib.import_module(module_path)
        asgi_app = getattr(module, obj_name)
    except Exception as exc:
        typer.echo(f"Error loading app {app_path!r}: {exc}", err=True)
        raise typer.Exit(1) from exc

    # Build a reverse map: path → name for named routes
    try:
        from buraq.urls import _route_registry
        path_to_name: dict[str, str] = {v: k for k, v in _route_registry.items()}
    except ImportError:
        path_to_name = {}

    # Unwrap Starlette/FastAPI middleware stack to reach the router
    router = getattr(asgi_app, "router", asgi_app)
    routes = getattr(router, "routes", [])

    if not routes:
        typer.echo("No routes found. Make sure the app is fully initialised.")
        raise typer.Exit(0)

    # Collect rows
    rows: list[tuple[str, str, str]] = []
    for route in routes:
        path_str = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or {"*"}
        method_str = ",".join(sorted(methods))
        name = path_to_name.get(path_str, getattr(route, "name", "") or "")
        rows.append((path_str, method_str, name))

    rows.sort(key=lambda r: r[0])

    # Calculate column widths
    w_path = max(len("Path"), *(len(r[0]) for r in rows))
    w_meth = max(len("Methods"), *(len(r[1]) for r in rows))
    w_name = max(len("Name"), *(len(r[2]) for r in rows))

    def _fmt(path: str, methods: str, name: str) -> str:
        return f"{path:<{w_path}}  {methods:<{w_meth}}  {name:<{w_name}}"

    header = _fmt("Path", "Methods", "Name")
    sep = "-" * len(header)
    typer.echo(header)
    typer.echo(sep)
    for path_str, method_str, name in rows:
        line = _fmt(path_str, method_str, name)
        if not no_color and name:
            line = f"\033[36m{line}\033[0m"
        typer.echo(line)

    typer.echo(f"\n{len(rows)} route(s) total.")


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
                typer.echo(
                    f"Module {app_name}.management.commands.{command} has no Command class.",
                    err=True,
                )
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


# ─── Shell ───────────────────────────────────────────────────────────────────

@app.command()
def shell(
    command: str | None = typer.Option(None, "--command", "-c", help="Python code to execute"),
    no_startup: bool = typer.Option(False, "--no-startup", help="Skip PYTHONSTARTUP script"),
):
    """
    Start an interactive Python shell with the Buraq environment pre-loaded.

    All models from INSTALLED_APPS and the Buraq db session are imported automatically.

    Example:
        python manage.py shell
        python manage.py shell -c "print(await Post.objects.count())"
    """
    import code
    import importlib

    from buraq.conf import settings

    local_ns: dict = {"settings": settings}

    # Auto-import all model modules from INSTALLED_APPS
    for app_name in settings.INSTALLED_APPS:
        for mod_name in ("models",):
            try:
                mod = importlib.import_module(f"{app_name}.{mod_name}")
                for attr in dir(mod):
                    obj = getattr(mod, attr)
                    if isinstance(obj, type) and hasattr(obj, "__tablename__"):
                        local_ns[attr] = obj
            except ModuleNotFoundError:
                pass

    # Import buraq built-ins
    try:
        from buraq.core.db import SessionLocal
        local_ns["SessionLocal"] = SessionLocal
    except ImportError:
        pass

    if command:
        exec(compile(command, "<string>", "exec"), local_ns)  # noqa: S102
        return

    _model_names = ", ".join(
        k for k, v in local_ns.items()
        if isinstance(v, type) and hasattr(v, "__tablename__")
    )
    banner = (
        f"Buraq interactive shell\n"
        f"Models available: {_model_names}\n"
        f"Type 'quit()' or Ctrl-D to exit."
    )
    code.interact(banner=banner, local=local_ns)


# ─── System Check ─────────────────────────────────────────────────────────────

@app.command("check")
def run_checks(
    deploy: bool = typer.Option(False, "--deploy", help="Run additional deployment checks"),
):
    """
    Run all system checks and print results.

    Example:
        python manage.py check
        python manage.py check --deploy
    """
    from buraq.checks.registry import registry

    messages = registry.run_checks()
    if not messages:
        typer.echo("System check identified no issues (0 silenced).")
        return

    errors = warnings = infos = 0
    for msg in messages:
        level = getattr(msg, "level", 0)
        if level >= 40:
            errors += 1
            label = typer.style("ERROR", fg=typer.colors.RED)
        elif level >= 30:
            warnings += 1
            label = typer.style("WARNING", fg=typer.colors.YELLOW)
        else:
            infos += 1
            label = typer.style("INFO", fg=typer.colors.BLUE)
        typer.echo(f"[{label}] {getattr(msg, 'id', '?')}: {getattr(msg, 'msg', msg)}")

    summary = f"System check identified {errors} error(s), {warnings} warning(s)."
    if errors:
        typer.echo(typer.style(summary, fg=typer.colors.RED), err=True)
        raise typer.Exit(1)
    typer.echo(summary)


# ─── DB Shell ─────────────────────────────────────────────────────────────────

@app.command()
def dbshell():
    """
    Open the database CLI for the configured DATABASE_URL.

    Supports SQLite (sqlite3), PostgreSQL (psql), and MySQL/MariaDB (mysql).

    Example:
        python manage.py dbshell
    """
    from sqlalchemy.engine import make_url as _make_url

    from buraq.conf import settings

    url = _make_url(settings.DATABASE_URL)
    dialect = url.get_dialect().name

    if dialect == "sqlite":
        db_path = url.database or ":memory:"
        cmd = ["sqlite3", db_path]
    elif dialect == "postgresql":
        host = url.host or "localhost"
        port = url.port or 5432
        user = url.username or ""
        db = url.database or ""
        cmd = ["psql", "-h", host, "-p", str(port), "-U", user, db]
    elif dialect in ("mysql", "mariadb"):
        host = url.host or "localhost"
        port = url.port or 3306
        user = url.username or ""
        db = url.database or ""
        cmd = ["mysql", "-h", host, f"--port={port}", f"-u{user}", db]
    else:
        typer.echo(f"Unsupported dialect: {dialect}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Connecting: {' '.join(cmd)}")
    subprocess.run(cmd)


# ─── Data Import/Export ───────────────────────────────────────────────────────

@app.command()
def dumpdata(
    output: str | None = typer.Option(
        None, "--output", "-o", help="Write to file instead of stdout"
    ),
    indent: int = typer.Option(2, "--indent", help="JSON indent level"),
    exclude: list[str] | None = typer.Option(
        None, "--exclude", "-e", help="Table names to exclude"
    ),
):
    """
    Dump all database data as JSON.

    Example:
        python manage.py dumpdata
        python manage.py dumpdata --output=fixtures/initial.json
        python manage.py dumpdata --exclude=buraq_users --exclude=buraq_sessions
    """
    _load_apps()
    import asyncio
    import json as _json

    from buraq.core.db import Base, SessionLocal

    exclude_set = set(exclude or [])

    async def _dump():
        tables = {
            name: table
            for name, table in Base.metadata.tables.items()
            if name not in exclude_set
        }
        result = {}
        async with SessionLocal() as db:
            import sqlalchemy as sa
            for name, table in tables.items():
                rows = (await db.execute(sa.select(table))).mappings().all()
                result[name] = [dict(row) for row in rows]
        return result

    data = asyncio.run(_dump())
    json_str = _json.dumps(data, indent=indent, default=str)

    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        typer.echo(f"Data written to {output}")
    else:
        typer.echo(json_str)


@app.command()
def loaddata(
    fixture: str = typer.Argument(..., help="Path to JSON fixture file"),
    table: list[str] | None = typer.Option(None, "--table", "-t", help="Load only these tables"),
):
    """
    Load data from a JSON fixture file into the database.

    Example:
        python manage.py loaddata fixtures/initial.json
        python manage.py loaddata fixtures/initial.json --table=buraq_users
    """
    _load_apps()
    import asyncio
    import json as _json

    from buraq.core.db import Base, SessionLocal

    fixture_data = _json.loads(Path(fixture).read_text(encoding="utf-8"))
    table_filter = set(table) if table else None

    async def _load():
        async with SessionLocal() as db:
            for table_name, rows in fixture_data.items():
                if table_filter and table_name not in table_filter:
                    continue
                sa_table = Base.metadata.tables.get(table_name)
                if sa_table is None:
                    typer.echo(f"  Skipping unknown table: {table_name}", err=True)
                    continue
                if not rows:
                    continue
                await db.execute(sa_table.insert(), rows)
                typer.echo(f"  Loaded {len(rows)} row(s) into '{table_name}'")
            await db.commit()

    asyncio.run(_load())
    typer.echo("Fixture loaded.")


# ─── Flush ────────────────────────────────────────────────────────────────────

@app.command()
def flush(
    no_input: bool = typer.Option(False, "--no-input", help="Do not prompt for confirmation"),
):
    """
    Delete all rows from all database tables without dropping the schema.

    Example:
        python manage.py flush
        python manage.py flush --no-input
    """
    _load_apps()
    import asyncio

    from buraq.core.db import Base, SessionLocal

    if not no_input:
        confirmed = typer.confirm(
            "This will DELETE ALL DATA from the database. Are you sure?", default=False
        )
        if not confirmed:
            typer.echo("Aborted.")
            raise typer.Exit(0)

    async def _flush():
        async with SessionLocal() as db:
            import sqlalchemy as sa
            for table in reversed(Base.metadata.sorted_tables):
                await db.execute(sa.delete(table))
            await db.commit()

    asyncio.run(_flush())
    typer.echo("All tables flushed.")


# ─── Change Password ──────────────────────────────────────────────────────────

@app.command()
def changepassword(
    username: str = typer.Argument(..., help="Username whose password to change"),
):
    """
    Change a user's password from the command line.

    Example:
        python manage.py changepassword admin
    """
    _load_apps()
    import asyncio
    import getpass

    from buraq.contrib.auth import make_password
    from buraq.contrib.auth.models import User

    pw1 = getpass.getpass(f"New password for '{username}': ")
    pw2 = getpass.getpass("Confirm password: ")
    if pw1 != pw2:
        typer.echo("Passwords do not match.", err=True)
        raise typer.Exit(1)
    if not pw1:
        typer.echo("Password cannot be empty.", err=True)
        raise typer.Exit(1)

    async def _change():
        user = await User.objects.get_or_none(username=username)
        if not user:
            typer.echo(f"User '{username}' not found.", err=True)
            raise typer.Exit(1)
        await User.objects.update(user.id, hashed_password=await make_password(pw1))
        typer.echo(f"Password for '{username}' changed successfully.")

    asyncio.run(_change())


# ─── Inspect DB ───────────────────────────────────────────────────────────────

@app.command()
def inspectdb(
    table: list[str] | None = typer.Option(None, "--table", "-t", help="Inspect only these tables"),
):
    """
    Generate model definitions by inspecting the existing database schema.

    Output is printed to stdout and can be redirected to a models.py file.

    Example:
        python manage.py inspectdb
        python manage.py inspectdb --table=posts --table=comments > models.py
    """
    import asyncio

    import sqlalchemy as sa

    from buraq.conf import settings

    _TYPE_MAP = {
        "INTEGER": "models.IntegerField()",
        "VARCHAR": "models.CharField(max_length=255)",
        "TEXT": "models.TextField()",
        "BOOLEAN": "models.BooleanField()",
        "FLOAT": "models.FloatField()",
        "NUMERIC": "models.DecimalField(max_digits=10, decimal_places=2)",
        "DATE": "models.DateField()",
        "DATETIME": "models.DateTimeField()",
        "TIMESTAMP": "models.DateTimeField()",
        "BLOB": "models.BinaryField()",
        "JSON": "models.JSONField()",
    }

    def _with_null_false(field_type: str) -> str:
        """
        Add null=False to a field expression.

        Trimming the closing paren and appending ", null=False)" yields
        `IntegerField(, null=False)` for any field that takes no arguments.
        """
        head, _, rest = field_type.partition("(")
        args = [a for a in [rest.rstrip(")")] if a]
        args.append("null=False")
        return f"{head}({', '.join(args)})"

    def _reflect(sync_conn):
        """
        Read the schema on the sync side of the async connection.

        An Inspector performs IO on every call, so it has to be *used* inside
        run_sync and not merely created there -- otherwise the first
        get_columns() raises MissingGreenlet.
        """
        inspector = sa.inspect(sync_conn)
        names = inspector.get_table_names()
        if table:
            names = [t for t in names if t in table]
        return [(name, inspector.get_columns(name)) for name in names]

    async def _inspect():
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(settings.DATABASE_URL)
        try:
            async with engine.connect() as conn:
                return await conn.run_sync(_reflect)
        finally:
            await engine.dispose()

    tables = asyncio.run(_inspect())

    lines = ["from buraq import models", ""]
    for tname, cols in tables:
        class_name = "".join(part.title() for part in tname.split("_"))
        lines.append(f"\nclass {class_name}(models.Model):")
        lines.append("    class Meta:")
        lines.append(f"        table_name = {tname!r}")
        for col in cols:
            if col["name"] == "id":
                continue
            col_type = str(col["type"]).upper().split("(")[0]
            field_type = _TYPE_MAP.get(col_type, "models.CharField(max_length=255)")
            if not col.get("nullable", True):
                field_type = _with_null_false(field_type)
            lines.append(f"    {col['name']} = {field_type}")

    typer.echo("\n".join(lines))


# ─── Diff Settings ────────────────────────────────────────────────────────────

@app.command()
def diffsettings(
    all_: bool = typer.Option(False, "--all", help="Show all settings, not just changed ones"),
):
    """
    Display settings that differ from Buraq's defaults.

    Example:
        python manage.py diffsettings
        python manage.py diffsettings --all
    """
    from buraq.conf import settings
    from buraq.conf.defaults import BuraqSettings

    defaults = BuraqSettings()
    current = settings

    for field_name in defaults.model_fields:
        default_val = getattr(defaults, field_name, None)
        current_val = getattr(current, field_name, None)
        changed = current_val != default_val
        if changed or all_:
            marker = "###" if changed else "   "
            typer.echo(f"{marker} {field_name} = {current_val!r}")
            if changed and all_:
                typer.echo(f"      (default: {default_val!r})")


# ─── Send Test Email ──────────────────────────────────────────────────────────

@app.command()
def sendtestemail(
    email: str = typer.Argument(..., help="Recipient email address"),
):
    """
    Send a test email to verify the email backend is configured correctly.

    Example:
        python manage.py sendtestemail admin@example.com
    """
    import asyncio

    from buraq.contrib.email.send import send_mail

    async def _send():
        await send_mail(
            subject="Buraq test email",
            message=(
                "If you received this email, your Buraq email configuration"
                " is working correctly.\n\n"
                "This is an automated test sent by the 'sendtestemail' management command."
            ),
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[email],
        )
        typer.echo(f"Test email sent to {email}.")

    asyncio.run(_send())


@app.command()
def sqlmigrate(
    revision: str = typer.Argument(..., help="Alembic revision ID"),
    backwards: bool = typer.Option(False, "--backwards", help="Show SQL for downgrade instead"),
):
    """
    Print the SQL for a migration without executing it.

    Example:
        python manage.py sqlmigrate abc123
        python manage.py sqlmigrate abc123 --backwards
    """
    direction = "downgrade" if backwards else "upgrade"
    result = subprocess.run(
        ["alembic", direction, "--sql", revision],
        capture_output=True,
        text=True,
    )
    typer.echo(result.stdout)
    if result.returncode != 0:
        typer.echo(result.stderr, err=True)
        raise typer.Exit(result.returncode)


@app.command()
def squashmigrations(
    start: str = typer.Argument(..., help="First revision to include in the squash"),
    end: str = typer.Argument("head", help="Last revision to include (default: head)"),
    name: str = typer.Option("squashed", "--name", "-n", help="Name for the squashed migration"),
):
    """
    Squash a range of migrations into a single migration file.

    This calls ``alembic merge`` to combine the given revisions into one,
    then stamps the database at the merge revision.

    Example:
        python manage.py squashmigrations abc123 head --name squashed_v2
    """
    result = subprocess.run(
        ["alembic", "merge", "--message", name, start, end],
        capture_output=True,
        text=True,
    )
    typer.echo(result.stdout)
    if result.returncode != 0:
        typer.echo(result.stderr, err=True)
        raise typer.Exit(result.returncode)
    typer.echo(f"Squashed migrations {start}..{end} into '{name}'.")


@app.command()
def createcachetable(
    table: str | None = typer.Option(
        None,
        "--table",
        help="Cache table name (defaults to the CACHE_TABLE setting)",
    ),
):
    """
    Create the database table used by DatabaseCache.

    Run this once after adding DatabaseCache to your CACHE_BACKEND setting.

    Example:
        python manage.py createcachetable
        python manage.py createcachetable --table=my_cache
    """
    import asyncio

    import sqlalchemy as sa

    from buraq.conf import settings
    from buraq.core.db import SessionLocal

    if table is None:
        table = getattr(settings, "CACHE_TABLE", None) or "buraq_cache_table"

    DDL = f"""
    CREATE TABLE IF NOT EXISTS {table} (
        cache_key VARCHAR(255) NOT NULL PRIMARY KEY,
        value     TEXT         NOT NULL,
        expires   DOUBLE PRECISION NOT NULL
    )
    """

    async def _create():
        async with SessionLocal() as db:
            await db.execute(sa.text(DDL))
            await db.commit()
        typer.echo(f"Cache table '{table}' created (or already exists).")

    asyncio.run(_create())


@app.command()
def clearsessions():
    """
    Delete all expired sessions from the database session table.

    Only relevant when using DatabaseSessionBackend. Cookie-based sessions
    don't need cleanup.

    Example:
        python manage.py clearsessions
    """
    import asyncio
    import time

    import sqlalchemy as sa

    from buraq.core.db import SessionLocal

    async def _clear():
        async with SessionLocal() as db:
            try:
                result = await db.execute(
                    sa.text(
                        "DELETE FROM buraq_sessions WHERE expire_date < :now"
                    ),
                    {"now": time.time()},
                )
                await db.commit()
                typer.echo(f"Deleted {result.rowcount} expired session(s).")
            except Exception as exc:
                typer.echo(
                    f"Could not clear sessions: {exc}\n"
                    "Make sure you are using DatabaseSessionBackend and the "
                    "buraq_sessions table exists.",
                    err=True,
                )
                raise typer.Exit(1) from exc

    asyncio.run(_clear())


@app.command("test")
def run_tests(
    paths: list[str] = typer.Argument(None, help="Test paths / modules (pytest syntax)"),
    verbosity: int = typer.Option(1, "--verbosity", "-v", help="Verbosity level (0-3)"),
    failfast: bool = typer.Option(False, "--failfast", "-x", help="Stop on first failure"),
    keepdb: bool = typer.Option(False, "--keepdb", help="Preserve test database between runs"),
    pattern: str = typer.Option(
        "test*.py", "--pattern", "-p", help="File pattern for test discovery"
    ),
    tag: list[str] = typer.Option([], "--tag", help="Run only tests with this tag"),
    exclude_tag: list[str] = typer.Option([], "--exclude-tag", help="Exclude tests with this tag"),
):
    """
    Discover and run the test suite using pytest.

    Automatically sets BURAQ_ENV=test so settings can branch on it.
    Supports all standard pytest options via -k, -x, -v etc.

    Example:
        python manage.py test
        python manage.py test posts tests/
        python manage.py test --failfast
        python manage.py test --verbosity=2
    """
    import os

    os.environ.setdefault("BURAQ_ENV", "test")

    pytest_args: list[str] = list(paths or [])

    v_flag = {0: "-q", 1: "", 2: "-v", 3: "-vv"}.get(verbosity, "-v")
    if v_flag:
        pytest_args.append(v_flag)
    if failfast:
        pytest_args.append("-x")
    if pattern != "test*.py":
        pytest_args += ["--ignore-glob", f"!{pattern}"]

    for t in tag:
        pytest_args += ["-m", t]

    result = subprocess.run([sys.executable, "-m", "pytest"] + pytest_args)
    raise typer.Exit(result.returncode)


# ─── Version ──────────────────────────────────────────────────────────────────

@app.command()
def version():
    """Print the installed Buraq version."""
    from buraq import __version__
    typer.echo(f"Buraq {__version__}")


# ─── Find Static ──────────────────────────────────────────────────────────────

@app.command()
def findstatic(
    path_: str = typer.Argument(..., help="Relative path of the static file to locate"),
    first: bool = typer.Option(False, "--first", help="Stop after the first match"),
):
    """
    Find and print the absolute path(s) of a static file as discovered by STATICFILES_FINDERS.

    Example:
        python manage.py findstatic css/style.css
        python manage.py findstatic images/logo.png --first
    """
    from buraq.contrib.staticfiles.finders import get_finders

    found: list[str] = []
    for finder in get_finders():
        result = finder.find(path_)
        if result:
            found.append(result)
            if first:
                break

    if not found:
        typer.echo(f"No static file found for {path_!r}", err=True)
        raise typer.Exit(1)

    for p in found:
        typer.echo(p)


# ─── Test Server ──────────────────────────────────────────────────────────────

@app.command()
def testserver(
    fixtures: list[str] = typer.Argument(..., help="Fixture files to load before starting server"),
    bind: str = typer.Option("main:app", "--app", help="ASGI app path (e.g. 'main:app')"),
    port: int = typer.Option(8000, help="Bind port"),
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    no_input: bool = typer.Option(False, "--no-input", help="Do not prompt for confirmation"),
):
    """
    Load fixtures into a temporary test database, then start the development server.

    Useful for manual QA with realistic data without touching the production database.

    Example:
        python manage.py testserver fixtures/posts.json fixtures/users.json
        python manage.py testserver fixtures/initial.json --port 8001
    """
    _load_apps()
    import asyncio
    import json as _json

    from buraq.core.db import Base, SessionLocal

    if not no_input and not typer.confirm(
        f"This will CLEAR the database and load {len(fixtures)} fixture(s). Continue?",
        default=False,
    ):
        typer.echo("Aborted.")
        raise typer.Exit(0)

    async def _load_fixtures():
        async with SessionLocal() as db:
            import sqlalchemy as sa

            # Flush all tables first
            for table in reversed(Base.metadata.sorted_tables):
                await db.execute(sa.delete(table))

            # Load each fixture
            for fixture_path in fixtures:
                fixture_data = _json.loads(Path(fixture_path).read_text(encoding="utf-8"))
                for table_name, rows in fixture_data.items():
                    sa_table = Base.metadata.tables.get(table_name)
                    if sa_table is None:
                        typer.echo(f"  Skipping unknown table: {table_name}", err=True)
                        continue
                    if rows:
                        await db.execute(sa_table.insert(), rows)
                        typer.echo(f"  Loaded {len(rows)} row(s) into '{table_name}'")
            await db.commit()

    typer.echo("Loading fixtures...")
    asyncio.run(_load_fixtures())
    typer.echo(f"Fixtures loaded. Starting server on http://{host}:{port} ...")

    try:
        from granian import Granian
        Granian(
            bind,
            address=host,
            port=port,
            interface="asgi",
            reload=False,
            working_dir=Path.cwd(),
        ).serve()
    except ImportError:
        import uvicorn
        uvicorn.run(bind, host=host, port=port, reload=False, log_level="debug")


# ─── SQL Flush ────────────────────────────────────────────────────────────────

@app.command()
def sqlflush():
    """
    Print the SQL statements that ``flush`` would execute, without running them.

    Useful for auditing what flush would do or generating a script to run later.

    Example:
        python manage.py sqlflush
        python manage.py sqlflush > flush.sql
    """
    _load_apps()
    import sqlalchemy as sa
    from sqlalchemy.dialects import sqlite as sqlite_dialect

    from buraq.core.db import Base

    dialect = sqlite_dialect.dialect()

    for table in reversed(Base.metadata.sorted_tables):
        stmt = sa.delete(table).compile(dialect=dialect)
        typer.echo(f"{stmt};")


# ─── SQL Sequence Reset ───────────────────────────────────────────────────────

@app.command()
def sqlsequencereset(
    apps: list[str] | None = typer.Argument(
        None, help="App names to reset sequences for (defaults to all apps)"
    ),
):
    """
    Print SQL to reset PostgreSQL sequences for tables belonging to the given apps.

    Only relevant for PostgreSQL — SQLite and MySQL use autoincrement instead.
    Run the output SQL via ``buraq dbshell`` after a bulk data import.

    Example:
        python manage.py sqlsequencereset
        python manage.py sqlsequencereset posts auth
    """
    _load_apps()
    from buraq.conf import settings
    from buraq.core.db import Base

    try:
        from sqlalchemy.engine import make_url as _make_url
        dialect = _make_url(settings.DATABASE_URL).get_dialect().name
    except Exception:
        dialect = "unknown"

    if dialect != "postgresql":
        typer.echo(
            f"Note: sequence reset is only needed for PostgreSQL (current dialect: {dialect}).",
            err=True,
        )
        if dialect not in ("postgresql",):
            raise typer.Exit(0)

    for table in Base.metadata.sorted_tables:
        # Match tables belonging to requested apps (based on table name prefix)
        if apps:
            matched = any(table.name.startswith(a) for a in apps)
            if not matched:
                continue

        # Find integer primary key columns
        for col in table.primary_key.columns:
            col_type = str(col.type).upper()
            if col.autoincrement and col_type in ("INTEGER", "BIGINTEGER", "BIGINT", "INT"):
                seq = f"{table.name}_{col.name}_seq"
                typer.echo(
                    f"SELECT setval('{seq}',"
                    f" COALESCE((SELECT MAX({col.name}) FROM {table.name}), 1), true);"
                )


# ─── Optimize Migration ───────────────────────────────────────────────────────

@app.command()
def optimizemigration(
    revisions: list[str] = typer.Argument(..., help="Two or more Alembic revision IDs to merge"),
    name: str = typer.Option("optimized", "--name", "-n", help="Name for the merged migration"),
):
    """
    Merge two or more Alembic branch heads into a single revision.

    This calls ``alembic merge`` to combine divergent migration heads, resolving
    branch splits after e.g. parallel feature development.

    Requires at least two revision IDs.

    Example:
        python manage.py optimizemigration abc1234 def5678
        python manage.py optimizemigration abc1234 def5678 --name merge_branches
    """
    if len(revisions) < 2:
        typer.echo(
            "Error: optimizemigration requires at least two revision IDs to merge.", err=True
        )
        raise typer.Exit(1)

    result = subprocess.run(
        ["alembic", "merge", "--message", name] + list(revisions),
        capture_output=True,
        text=True,
    )
    typer.echo(result.stdout)
    if result.returncode != 0:
        typer.echo(result.stderr, err=True)
        raise typer.Exit(result.returncode)
    typer.echo(f"Merged {len(revisions)} revisions as '{name}'.")


# ─── Remove Stale Content Types ───────────────────────────────────────────────

@app.command()
def remove_stale_contenttypes(
    no_input: bool = typer.Option(False, "--no-input", help="Do not prompt — delete automatically"),
    include_stale_apps: bool = typer.Option(
        False, "--include-stale-apps",
        help="Remove content types even for apps still in INSTALLED_APPS",
    ),
):
    """
    Remove ContentType records for models that no longer exist.

    After removing an app or model from INSTALLED_APPS, run this to clean
    up orphaned ContentType rows so the database stays consistent.

    Example:
        python manage.py remove_stale_contenttypes
        python manage.py remove_stale_contenttypes --no-input
    """
    _load_apps()
    import asyncio
    import importlib

    from sqlalchemy.exc import OperationalError

    from buraq.conf import settings

    # The model lives in .models -- importing it from the package raised
    # ImportError on every run, and `if not ContentType` could never have
    # caught that anyway since a class is always truthy.
    try:
        from buraq.contrib.contenttypes.models import ContentType
    except ImportError:
        typer.echo(
            "buraq.contrib.contenttypes is not installed or ContentType model is unavailable.",
            err=True,
        )
        raise typer.Exit(1) from None

    async def _clean():
        all_cts = await ContentType.objects.all()
        if not all_cts:
            typer.echo("No ContentType records found.")
            return

        stale = []
        installed = set(settings.INSTALLED_APPS)

        for ct in all_cts:
            app_label = ct.app_label
            model_name = ct.model

            if not include_stale_apps and app_label not in installed:
                stale.append(ct)
                continue

            # Try to import the model class
            try:
                for app_name in installed:
                    try:
                        mod = importlib.import_module(f"{app_name}.models")
                        if hasattr(mod, model_name.title()):
                            break
                    except ModuleNotFoundError:
                        pass
                else:
                    stale.append(ct)
            except Exception:
                stale.append(ct)

        if not stale:
            typer.echo("No stale content types found.")
            return

        typer.echo(f"Found {len(stale)} stale content type(s):")
        for ct in stale:
            typer.echo(f"  - {ct.app_label}.{ct.model}")

        if not no_input and not typer.confirm("Delete these content types?", default=False):
            typer.echo("Aborted.")
            return

        for ct in stale:
            await ct.delete()
        typer.echo(f"Deleted {len(stale)} stale content type(s).")

    try:
        asyncio.run(_clean())
    except OperationalError:
        # contenttypes is optional: without it in INSTALLED_APPS the table was
        # never created, which is a setup answer rather than a stack trace.
        typer.secho(
            "No contenttypes table found. Add 'buraq.contrib.contenttypes' to "
            "INSTALLED_APPS and run `buraq migrate` before using this command.",
            fg="yellow",
        )
        raise typer.Exit(1) from None


@app.command()
def worker(
    queue: str = typer.Option("default", "--queue", "-q", help="Queue name to consume."),
    concurrency: int = typer.Option(
        1, "--concurrency", "-c", help="Number of concurrent task coroutines."
    ),
    poll_interval: float = typer.Option(
        1.0, "--poll-interval", help="Seconds between database polls (DatabaseBackend only)."
    ),
    max_tasks: int = typer.Option(
        0, "--max-tasks", help="Stop after processing this many tasks (0 = run forever)."
    ),
):
    """
    Run the background task worker.

    Polls the task backend for pending tasks and executes them.
    Uses the backend configured in settings.TASKS['default'].

    \b
    Examples:
        buraq worker
        buraq worker --queue high-priority --concurrency 4
        buraq worker --queue email --poll-interval 0.5
    """
    import asyncio
    import signal

    async def _run():
        from buraq.conf import settings
        from buraq.utils.module_loading import import_string

        tasks_config: dict = getattr(settings, "TASKS", {})
        backend_path = tasks_config.get("default", {}).get(
            "BACKEND", "buraq.contrib.tasks.backends.db.DatabaseBackend"
        )

        try:
            backend_cls = import_string(backend_path)
        except ImportError as exc:
            typer.echo(f"Error: cannot import task backend {backend_path!r}: {exc}", err=True)
            raise typer.Exit(1) from exc

        backend_cls()  # validate the backend can be instantiated
        typer.echo(
            f"Worker started — queue={queue!r} concurrency={concurrency} backend={backend_path}"
        )

        # DummyBackend has no pending tasks to poll — warn and exit.
        if "dummy" in backend_path.lower():
            typer.echo(
                "DummyBackend executes tasks immediately in-process — no worker needed.", err=True
            )
            return

        processed = 0
        stop = False

        def _handle_signal(sig, frame):
            nonlocal stop
            typer.echo("\nShutting down worker…")
            stop = True

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        try:
            from datetime import UTC, datetime

            import sqlalchemy as sa

            from buraq.contrib.tasks.backends.db import _import_func, buraq_task_table
            from buraq.contrib.tasks.result import TaskStatus
            from buraq.core.db import SessionLocal
        except ImportError as exc:
            typer.echo(f"DatabaseBackend requires buraq database setup: {exc}", err=True)
            raise typer.Exit(1) from exc

        semaphore = asyncio.Semaphore(concurrency)

        async def _execute_task(row):
            nonlocal processed
            async with semaphore:
                import inspect
                import json
                func = _import_func(row.func_path)
                args = json.loads(row.args_json or "[]")
                kwargs = json.loads(row.kwargs_json or "{}")

                async with SessionLocal() as db:
                    await db.execute(
                        buraq_task_table.update()
                        .where(buraq_task_table.c.id == row.id)
                        .values(status=TaskStatus.RUNNING.value, started_at=datetime.now(UTC),
                                attempts=row.attempts + 1)
                    )
                    await db.commit()

                try:
                    if inspect.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = await asyncio.to_thread(func, *args, **kwargs)
                    return_json = json.dumps(result) if result is not None else None
                    status = TaskStatus.SUCCEEDED.value
                    error = None
                except Exception as exc:
                    return_json = None
                    status = TaskStatus.FAILED.value
                    error = repr(exc)

                async with SessionLocal() as db:
                    await db.execute(
                        buraq_task_table.update()
                        .where(buraq_task_table.c.id == row.id)
                        .values(status=status, return_json=return_json, error=error,
                                finished_at=datetime.now(UTC))
                    )
                    await db.commit()

                icon = "✓" if status == TaskStatus.SUCCEEDED.value else "✗"
                typer.echo(f"  {icon} {row.func_path} [{row.id[:8]}]")
                processed += 1

        while not stop:
            async with SessionLocal() as db:
                result = await db.execute(
                    sa.select(buraq_task_table)
                    .where(
                        buraq_task_table.c.queue == queue,
                        buraq_task_table.c.status == TaskStatus.PENDING.value,
                    )
                    .order_by(
                        buraq_task_table.c.priority.asc(),
                        buraq_task_table.c.created_at.asc(),
                    )
                    .limit(concurrency)
                )
                rows = result.fetchall()

            if rows:
                await asyncio.gather(*[_execute_task(row) for row in rows])
            else:
                await asyncio.sleep(poll_interval)

            if max_tasks and processed >= max_tasks:
                typer.echo(f"Reached max-tasks={max_tasks}. Stopping.")
                break

        typer.echo(f"Worker stopped. Processed {processed} task(s).")

    asyncio.run(_run())


def execute_from_command_line(argv=None):
    """Entry point for manage.py."""
    import sys
    app(args=(argv or sys.argv)[1:], standalone_mode=True)


if __name__ == "__main__":
    app()
