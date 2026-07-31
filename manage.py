#!/usr/bin/env python
"""
Buraq management CLI.
Works like Django's manage.py — just run:  python manage.py <command>
"""
import os
import sys
from pathlib import Path

def _bootstrap():
    root = Path(__file__).parent.resolve()
    venv = root / ".venv"

    python = venv / "Scripts" / "python.exe"   # Windows
    if not python.exists():
        python = venv / "bin" / "python"        # Unix/macOS

    if python.exists() and Path(sys.executable).resolve() != python.resolve():
        os.execv(str(python), [str(python)] + sys.argv)

_bootstrap()

from buraq.management.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
