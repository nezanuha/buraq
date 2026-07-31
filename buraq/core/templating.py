from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from buraq.conf import settings

_templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        templates_dir = settings.TEMPLATES_DIR or str(Path.cwd() / "templates")
        _templates = Jinja2Templates(directory=templates_dir)
        _templates.env.auto_reload = settings.DEBUG
        # Inject commonly needed helpers as Jinja2 globals
        from buraq.contrib.messages import get_messages
        _templates.env.globals["get_messages"] = get_messages
    return _templates


def register_static(app: FastAPI) -> None:
    static_dir = settings.STATIC_DIR or str(Path.cwd() / "static")
    if Path(static_dir).exists():
        app.mount(settings.STATIC_URL.rstrip("/"), StaticFiles(directory=static_dir), name="static")

    if settings.MEDIA_DIR and Path(settings.MEDIA_DIR).exists():
        app.mount(
            settings.MEDIA_URL.rstrip("/"),
            StaticFiles(directory=settings.MEDIA_DIR),
            name="media",
        )
