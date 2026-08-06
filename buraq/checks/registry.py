from __future__ import annotations

from typing import Callable


class CheckMessage:
    level: int = 0

    def __init__(self, msg: str, *, hint: str | None = None, obj=None, id: str = ""):
        self.msg = msg
        self.hint = hint
        self.obj = obj
        self.id = id

    def __str__(self):
        return self.msg

    def __repr__(self):
        return f"{self.__class__.__name__}({self.msg!r}, id={self.id!r})"


class Debug(CheckMessage):
    level = 10


class Info(CheckMessage):
    level = 20


class Warning(CheckMessage):
    level = 30


class Error(CheckMessage):
    level = 40


class Critical(CheckMessage):
    level = 50


class CheckRegistry:
    def __init__(self):
        self._checks: list[Callable] = []

    def register(self, fn: Callable | None = None, *tags):
        if fn is None:
            def decorator(f):
                self._checks.append(f)
                return f
            return decorator
        self._checks.append(fn)
        return fn

    def run_checks(self, tags=None) -> list[CheckMessage]:
        from buraq.conf import settings
        messages = []
        for check in self._checks:
            try:
                result = check(settings) or []
                messages.extend(result)
            except Exception as e:
                messages.append(Error(
                    f"Check {check.__name__!r} raised {type(e).__name__}: {e}",
                    id="checks.E001",
                ))
        return messages

    def run_checks_or_raise(self) -> None:
        """Run all checks; raise ImproperlyConfigured if any Error-level messages exist in non-DEBUG mode."""
        from buraq.conf import settings
        messages = self.run_checks()
        errors = [m for m in messages if m.level >= Error.level]
        if errors:
            if settings.DEBUG:
                import sys
                summary = "; ".join(f"[{e.id}] {e.msg}" for e in errors)
                print(
                    f"SystemCheck: {len(errors)} error(s) found (DEBUG mode — startup not blocked): {summary}",
                    file=sys.stderr,
                )
            else:
                from buraq.exceptions import ImproperlyConfigured
                summary = "; ".join(f"[{e.id}] {e.msg}" for e in errors)
                raise ImproperlyConfigured(
                    f"System checks found {len(errors)} error(s): {summary}"
                )


registry = CheckRegistry()
