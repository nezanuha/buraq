"""
The ETag decorator hashed the response body twice on every request.

The digest was computed for the header, then computed again to compare against
If-None-Match -- the same bytes, the same result, thrown away the first time.
On a 1 MB response that is about 2.2ms of pure waste per request.

Every md5 here is a cache key, an ETag or a file digest -- never a security
decision -- so each call says usedforsecurity=False. Without it, hashlib refuses
to construct md5 at all on a FIPS-enabled build, and Buraq would not start.
"""

import hashlib
import pathlib

import pytest


def _sources():
    return {
        p: p.read_text(encoding="utf-8")
        for p in pathlib.Path("buraq").rglob("*.py")
        if "hashlib.md5(" in p.read_text(encoding="utf-8")
    }


def test_every_md5_declares_it_is_not_for_security():
    """Otherwise the process cannot start on a FIPS-enabled system."""
    offenders = []
    for path, src in _sources().items():
        for number, line in enumerate(src.splitlines(), 1):
            # func.md5(col) is SQL, run by the database -- not this process.
            if "hashlib.md5(" in line and "usedforsecurity" not in line:
                offenders.append(f"{path}:{number}")
    assert not offenders, "md5 without usedforsecurity=False: " + ", ".join(offenders)


def test_the_conditional_page_decorator_hashes_once():
    src = pathlib.Path("buraq/decorators.py").read_text(encoding="utf-8")
    start = src.index("def conditional_page(")
    end = src.find("\ndef ", start + 1)
    body = src[start:] if end == -1 else src[start:end]
    assert body.count("md5(") == 1, "the response body should be hashed once and reused"


def test_md5_is_constructible_with_the_flag():
    """The flag is accepted on this interpreter, so the calls are valid."""
    assert hashlib.md5(b"x", usedforsecurity=False).hexdigest() == hashlib.md5(b"x").hexdigest()


@pytest.mark.parametrize("size", [1_000, 100_000])
def test_one_hash_matches_two(size):
    """Reusing the digest must not change the ETag it produces."""
    body = b"a" * size
    digest = hashlib.md5(body, usedforsecurity=False).hexdigest()
    assert digest == hashlib.md5(body, usedforsecurity=False).hexdigest()
