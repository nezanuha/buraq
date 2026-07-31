"""
Django-style flash messages — backed by session so they survive redirects.

Usage in views:
    from buraq.contrib.messages import success, error, info, warning

    async def create_post(request):
        ...
        success(request, "Post created successfully!")
        return redirect("/posts/")

    async def post_list(request):
        msgs = get_messages(request)
        return render(request, "posts/list.html", {"messages": msgs})

In templates (Jinja2):
    {% for message in messages %}
        <div class="alert alert-{{ message.tags }}">{{ message }}</div>
    {% endfor %}

Requires buraq.contrib.sessions.middleware.SessionMiddleware (registered by default).
"""
from buraq.contrib.messages.storage import DEBUG, ERROR, INFO, SUCCESS, WARNING, Message

_SESSION_KEY = "_messages"


def _get_queued(request) -> list:
    session = getattr(request, "session", None)
    if session is None:
        return []
    return session.get(_SESSION_KEY, [])


def _set_queued(request, messages: list) -> None:
    session = getattr(request, "session", None)
    if session is not None:
        session[_SESSION_KEY] = messages


def get_messages(request) -> list[Message]:
    """Return all queued messages and remove them from the session."""
    raw = _get_queued(request)
    _set_queued(request, [])
    return [Message(**m) for m in raw]


def add_message(request, level: int, message: str, extra_tags: str = "") -> None:
    queued = _get_queued(request)
    queued.append({"level": level, "message": message, "extra_tags": extra_tags})
    _set_queued(request, queued)


def debug(request, message: str, extra_tags: str = "") -> None:
    add_message(request, DEBUG, message, extra_tags)


def info(request, message: str, extra_tags: str = "") -> None:
    add_message(request, INFO, message, extra_tags)


def success(request, message: str, extra_tags: str = "") -> None:
    add_message(request, SUCCESS, message, extra_tags)


def warning(request, message: str, extra_tags: str = "") -> None:
    add_message(request, WARNING, message, extra_tags)


def error(request, message: str, extra_tags: str = "") -> None:
    add_message(request, ERROR, message, extra_tags)
