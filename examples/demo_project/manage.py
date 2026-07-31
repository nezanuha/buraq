#!/usr/bin/env python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from buraq.management.cli import app

if __name__ == "__main__":
    app()
