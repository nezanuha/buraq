"""
BaseCommand — like Django's django.core.management.base.BaseCommand.

Usage:
    # myapp/management/commands/send_reminders.py
    from buraq.management.base import BaseCommand

    class Command(BaseCommand):
        help = "Send reminder emails to users due for follow-up"

        def add_arguments(self, parser):
            parser.add_argument("--days", type=int, default=7, help="Look back N days")
            parser.add_argument("--dry-run", action="store_true")

        async def handle(self, *args, **options):
            days = options["days"]
            dry_run = options["dry_run"]
            self.stdout.write(f"Scanning past {days} days...")
            # ... your logic here ...
            self.stdout.write(self.style.SUCCESS("Done!"))

Then run:
    python manage.py manage send_reminders --days=14
"""
import argparse
import asyncio
import sys
from typing import Any


class Style:
    """Terminal color helpers — mirrors Django's management style."""

    def SUCCESS(self, msg: str) -> str:
        return f"\033[32m{msg}\033[0m"  # green

    def ERROR(self, msg: str) -> str:
        return f"\033[31m{msg}\033[0m"  # red

    def WARNING(self, msg: str) -> str:
        return f"\033[33m{msg}\033[0m"  # yellow

    def NOTICE(self, msg: str) -> str:
        return f"\033[34m{msg}\033[0m"  # blue

    def HTTP_INFO(self, msg: str) -> str:
        return f"\033[36m{msg}\033[0m"  # cyan

    def MIGRATE_HEADING(self, msg: str) -> str:
        return f"\033[1m{msg}\033[0m"  # bold

    def MIGRATE_LABEL(self, msg: str) -> str:
        return f"\033[36m{msg}\033[0m"  # cyan

    def SQL_FIELD(self, msg: str) -> str:
        return f"\033[33m{msg}\033[0m"  # yellow

    # Lowercase aliases for convenience
    success = SUCCESS
    error = ERROR
    warning = WARNING
    notice = NOTICE
    http_info = HTTP_INFO
    migrate_heading = MIGRATE_HEADING
    migrate_label = MIGRATE_LABEL
    sql_field = SQL_FIELD


class CommandError(Exception):
    """Exception raised by management commands."""
    def __init__(self, message: str = "", returncode: int = 1):
        self.returncode = returncode
        super().__init__(message)


class SystemCheckError(CommandError):
    pass


class BaseCommand:
    """
    Base class for all Buraq management commands.

    Subclass this in <app>/management/commands/<name>.py
    and define handle() as an async method.
    """

    help: str = ""
    requires_migrations_checks: bool = False
    requires_system_checks: bool = False
    suppressed_base_arguments: set = set()

    def __init__(self, stdout=None, stderr=None, no_color: bool = False):
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.style = Style()

    # ── Override in subclass ────────────────────────────────────────────────

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Override to add command-line arguments."""
        pass

    async def handle(self, *args, **options) -> Any:
        """The actual command logic. Must be overridden."""
        raise NotImplementedError(
            "Subclasses of BaseCommand must provide a handle() method."
        )

    # ── Internal ────────────────────────────────────────────────────────────

    def create_parser(self, prog_name: str, subcommand: str) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog=f"{prog_name} {subcommand}",
            description=self.help or None,
        )
        self.add_arguments(parser)
        return parser

    def print_help(self, prog_name: str, subcommand: str) -> None:
        parser = self.create_parser(prog_name, subcommand)
        parser.print_help(self.stdout)

    def execute(self, *args, **options) -> Any:
        """Run handle() — call this from CLI."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # Inside an already-running loop (e.g., tests with pytest-asyncio).
                # Schedule as a task; callers must await or use asyncio.ensure_future.
                future = asyncio.ensure_future(self.handle(*args, **options))
                return future
            return asyncio.run(self.handle(*args, **options))
        except CommandError as e:
            self.stderr.write(self.style.error(f"CommandError: {e}"))
            raise SystemExit(e.returncode) from e

    def run_from_argv(self, argv: list) -> None:
        """Parse argv and execute the command."""
        subcommand = argv[1] if len(argv) > 1 else ""
        parser = self.create_parser(argv[0], subcommand)
        options = vars(parser.parse_args(argv[2:]))
        self.execute(**options)
