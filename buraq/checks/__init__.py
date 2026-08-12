"""
System checks framework — validates configuration at startup.

Usage:
    from buraq.checks import register, run_checks, Error, Warning

    @register
    def check_my_setting(settings, **kwargs):
        if not settings.MY_API_KEY:
            return [Error("MY_API_KEY is not set.", id="myapp.E001")]
        return []

    # Run all registered checks:
    messages = run_checks()
    for msg in messages:
        print(f"[{msg.__class__.__name__}] {msg.id}: {msg}")
"""
# Register built-in security checks
import buraq.checks.security  # noqa: F401, E402
from buraq.checks.registry import (
    CheckMessage,
    Critical,
    Debug,
    Error,
    Info,
    Warning,
    registry,
)

register = registry.register


def run_checks(tags=None) -> list[CheckMessage]:
    return registry.run_checks(tags=tags)


__all__ = [
    "register", "run_checks",
    "CheckMessage", "Debug", "Info", "Warning", "Error", "Critical",
]
