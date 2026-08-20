"""
Entry point for ``python -m buraq``.

The console script is the usual way in, but it only works when its directory is
on PATH — which it is not for a pip install into an unactivated environment. The
module form always works, because you name the interpreter yourself.
"""

from buraq.management.cli import app

if __name__ == "__main__":
    app()
