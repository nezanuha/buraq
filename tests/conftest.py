"""
Shared test configuration.

The settings layer refuses to import with a default/insecure SECRET_KEY, and
`.env` is gitignored — so a fresh clone could not run `pytest` at all until the
developer hand-created one. Setting the environment here keeps the suite
hermetic: no `.env`, no local database, no external state required.

Must run before any `buraq` import, so this file only touches os.environ at
module level and imports nothing from the package.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-used-outside-the-suite")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
