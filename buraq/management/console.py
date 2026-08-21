"""
One vocabulary for command output.

Commands printed with bare `typer.echo`, so every one chose its own wording and
nothing was distinguishable at a glance: an error read the same as a note. These
helpers give the CLI a small, consistent set of shapes.

Symbols degrade to ASCII where the terminal cannot encode them. A Windows
console defaults to cp1252, which turns a tick into a replacement character --
worse than the plain marker it replaced.
"""

from __future__ import annotations

import sys

import typer

_FANCY = {"ok": "✓", "warn": "▲", "err": "✗", "step": "→", "dot": "·"}
_PLAIN = {"ok": "+", "warn": "!", "err": "x", "step": ">", "dot": "-"}


def _symbols() -> dict[str, str]:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "".join(_FANCY.values()).encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return _PLAIN
    return _FANCY


SYM = _symbols()


def success(message: str) -> None:
    """Something finished and produced the result the user wanted."""
    typer.secho(f"{SYM['ok']} {message}", fg=typer.colors.GREEN)


def warn(message: str) -> None:
    """Worth knowing, but the command carried on."""
    typer.secho(f"{SYM['warn']} {message}", fg=typer.colors.YELLOW)


def error(message: str) -> None:
    """The command could not do what was asked."""
    typer.secho(f"{SYM['err']} {message}", fg=typer.colors.RED, err=True)


def step(message: str) -> None:
    """Announce work about to happen."""
    typer.secho(f"{SYM['step']} {message}", fg=typer.colors.CYAN)


def note(message: str) -> None:
    """Context beneath a step: quieter than the line it explains."""
    typer.secho(f"  {message}", dim=True)


def item(message: str) -> None:
    """A member of a list the command is reporting."""
    typer.secho(f"  {SYM['dot']} {message}")


def hint(message: str) -> None:
    """What to do next, after something went wrong or nothing happened."""
    typer.secho(f"  {message}", fg=typer.colors.BRIGHT_BLACK)
