"""
Command output.

Commands printed through bare `typer.echo`, so nothing was distinguishable at a
glance and alembic's own setup chatter — the same three lines on every run —
buried what the command had actually done.
"""

import sys

import pytest

from buraq.management import console


def test_symbols_fall_back_where_the_terminal_cannot_encode_them(monkeypatch):
    """
    A Windows console defaults to cp1252, which renders a tick as a replacement
    character: worse than the plain marker it replaced.
    """
    class Cp1252Stdout:
        encoding = "cp1252"

    monkeypatch.setattr(sys, "stdout", Cp1252Stdout())

    assert console._symbols() == console._PLAIN


def test_symbols_are_used_where_the_terminal_can_encode_them(monkeypatch):
    class Utf8Stdout:
        encoding = "utf-8"

    monkeypatch.setattr(sys, "stdout", Utf8Stdout())

    assert console._symbols() == console._FANCY


def test_a_stream_with_no_encoding_is_treated_as_ascii(monkeypatch):
    class Anonymous:
        pass

    monkeypatch.setattr(sys, "stdout", Anonymous())

    assert console._symbols() == console._PLAIN


@pytest.mark.parametrize(
    "write,expected",
    [
        (console.success, "ok"),
        (console.warn, "warn"),
        (console.error, "err"),
        (console.step, "step"),
    ],
)
def test_each_level_is_marked_distinctly(write, expected, capsys):
    write("something happened")

    stream = capsys.readouterr()
    printed = stream.out + stream.err
    assert console.SYM[expected] in printed
    assert "something happened" in printed


def test_alembic_setup_chatter_is_recognised():
    """These three lines appear on every run and say nothing about the migration."""
    from buraq.management.cli import _ALEMBIC_NOISE

    samples = [
        "INFO  [alembic.runtime.migration] Context impl SQLiteImpl.",
        "INFO  [alembic.runtime.migration] Will assume non-transactional DDL.",
        "INFO  [alembic.runtime.plugins] setting up autogenerate plugin x",
    ]
    for line in samples:
        assert any(noise in line for noise in _ALEMBIC_NOISE), line


def test_migration_progress_is_not_treated_as_chatter():
    """The lines that report actual work must survive the filter."""
    from buraq.management.cli import _ALEMBIC_NOISE

    keep = [
        "INFO  [alembic.runtime.migration] Running upgrade  -> abc123, initial",
        "INFO  [alembic.autogenerate.compare.tables] Detected added table 'posts'",
    ]
    for line in keep:
        assert not any(noise in line for noise in _ALEMBIC_NOISE), line
