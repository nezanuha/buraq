"""
Buraq feature audit script.

Fully automatic — no manual registry, no hardcoded names.

Runs three independent checks derived entirely from the source tree:

  docs      — every public symbol appears somewhere in docs/
  exports   — for files that define __all__, every public symbol is listed
              and every entry in __all__ actually exists
  dupes     — no public name is defined in more than one source file

Usage:
    python scripts/audit.py                        # all checks (default)
    python scripts/audit.py --fail                 # only failures
    python scripts/audit.py --check docs           # doc coverage only
    python scripts/audit.py --check exports        # __all__ consistency only
    python scripts/audit.py --check dupes          # duplicate names only
    python scripts/audit.py --module orm           # filter by path substring
    python scripts/audit.py --min-len 4            # skip short names (default: 4)
    python scripts/audit.py --no-docs              # alias for --check exports,dupes
"""
from __future__ import annotations

import argparse
import ast
import io
import sys
from dataclasses import dataclass
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
SRC  = ROOT / "buraq"
#: Documentation sources only. The site now builds into docs/dist, which holds a
#: rendered copy of every page plus a generated .md per route -- scanning those
#: would let a stale build vouch for a symbol the sources no longer mention.
DOCS = ROOT / "docs" / "src" / "content"


def _doc_files():
    """Every documentation page, .md and .mdx alike."""
    yield from sorted(DOCS.rglob("*.md"))
    yield from sorted(DOCS.rglob("*.mdx"))

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
ORANGE = "\033[38;5;214m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

# ── Skip configuration (all zero-maintenance) ─────────────────────────────────

SKIP_PATHS = {
    "__pycache__",
    "migrations",
    "vendor",
    "core",    # internal JWT / db wiring
    "checks",  # internal system-check framework
}

SKIP_NAMES = {
    "main", "setup", "register", "get", "post", "put", "patch", "delete",
    "head", "options", "trace",
    # Auth internals
    "GroupPermission", "get_password_validators", "render_to_string_safe",
    # Cache internals
    "BaseCacheBackend", "CacheExtension",
    # Auth internals
    "verify_password",
    # Messages internals
    "MessageStorage",
    # Static file internals
    "get_finders", "get_files", "StaticExtension",
    # Form metaclasses / internals
    "MediaDefiningClass", "DeclarativeFieldsMetaclass", "ModelFormMetaclass",
    "ManagementForm",
    # Serializer internals
    "register_serializer", "SerializationError", "DeserializationError",
    # URL internals
    "I18nURLGroup",
    # Admin internals
    "get_admin_router", "get_column_type", "get_form_fields",
    "obj_to_dict", "coerce_form_data",
    # Utils internals
    "classproperty", "get_current_timezone_name",
    "warmup_catalogs", "invalidate_cache",
    # CLI internals
    "pip_run", "run_command", "run_tests",
}

SKIP_SUFFIXES = (
    "_filter",
    "Handler",
    "Meta",
)

SKIP_SOURCE_PATHS = (
    "template/builtins",
    "utils/log.py",
    "utils/feedgenerator",
    "auth/schemas.py",
    "staticfiles/handlers.py",
    "contrib/messages/storage.py",
    "utils/formats.py",
    "utils/timezone.py",
)


# ── AST helpers ───────────────────────────────────────────────────────────────

@dataclass
class Symbol:
    rel_path: str
    name: str
    kind: str       # "class" | "function"
    line: int


@dataclass
class FileData:
    rel_path: str
    symbols: list[Symbol]           # public top-level classes & functions (filtered for audit)
    all_names: list[str] | None     # __all__ contents, or None if not defined
    imported_names: set[str]        # names imported at top level
    assigned_names: set[str]        # names assigned at top level (Foo = Bar)
    defined_names: set[str]         # ALL top-level class/function names (no filtering — for phantom check)


def _extract_all(tree: ast.Module) -> list[str] | None:
    """Return the list of string literals in __all__, or None if not defined."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    return [
                        elt.value
                        for elt in node.value.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    ]
    return None


def _extract_imports(tree: ast.Module) -> set[str]:
    """Names imported at the top level (handles aliased and star-less imports)."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name)
    return names


def _extract_assignments(tree: ast.Module) -> set[str]:
    """Top-level simple assignments: Foo = ..."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
    return names


def _is_auditable(rel: Path) -> bool:
    for part in rel.parts:
        if part in SKIP_PATHS:
            return False
    return True


def _is_public_symbol(name: str, rel_str: str, min_len: int) -> bool:
    if name.startswith("_"):
        return False
    if name in SKIP_NAMES:
        return False
    if len(name) < min_len:
        return False
    if name.endswith(SKIP_SUFFIXES):
        return False
    if any(s in rel_str for s in SKIP_SOURCE_PATHS):
        return False
    return True


# ── Collection ────────────────────────────────────────────────────────────────

def _collect(min_len: int, filter_module: str | None) -> list[FileData]:
    files: list[FileData] = []

    for py_file in sorted(SRC.rglob("*.py")):
        rel = py_file.relative_to(ROOT)
        rel_str = rel.as_posix()

        if not _is_auditable(rel):
            continue
        if filter_module and filter_module not in rel_str:
            continue

        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
            tree   = ast.parse(source)
        except SyntaxError:
            continue

        symbols: list[Symbol] = []
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                if _is_public_symbol(name, rel_str, min_len):
                    symbols.append(Symbol(rel_str, name, kind, node.lineno))

        all_names = _extract_all(tree)
        imported  = _extract_imports(tree)
        assigned  = _extract_assignments(tree)

        # All top-level class/function names, unfiltered — used for phantom check
        defined: set[str] = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        }

        files.append(FileData(rel_str, symbols, all_names, imported, assigned, defined))

    return files


# ── Checks ────────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    rel_path: str
    name: str
    line: int
    kind: str    # "doc_gap" | "all_missing" | "all_phantom" | "dupe"
    detail: str = ""


def check_docs(files: list[FileData]) -> list[Finding]:
    """Every public symbol should appear in at least one docs page."""
    doc_texts: list[tuple[str, str]] = []
    for df in _doc_files():
        try:
            doc_texts.append((
                df.relative_to(ROOT).as_posix(),
                df.read_text(encoding="utf-8", errors="ignore"),
            ))
        except Exception:
            pass

    findings: list[Finding] = []
    for fd in files:
        for sym in fd.symbols:
            if not any(sym.name in text for _, text in doc_texts):
                findings.append(Finding(sym.rel_path, sym.name, sym.line, "doc_gap"))
    return findings


def check_exports(files: list[FileData]) -> list[Finding]:
    """
    For files that define __all__:
    - flag public symbols (class/function) not listed in __all__
    - flag __all__ entries that have no definition or import in the file
    """
    findings: list[Finding] = []

    for fd in files:
        if fd.all_names is None:
            continue  # file has no __all__ — skip

        all_set = set(fd.all_names)

        # All names available in the file — use defined_names (unfiltered) for phantom
        # check so short names (Now, Chr, etc.) don't produce false positives.
        available = fd.defined_names | fd.imported_names | fd.assigned_names

        # Auditable public class/function defined here but not exported
        for sym in fd.symbols:
            if sym.name not in all_set:
                findings.append(Finding(
                    sym.rel_path, sym.name, sym.line, "all_missing",
                    detail="defined here but not in __all__",
                ))

        # __all__ entries that have no corresponding definition or import
        for name in fd.all_names:
            if name not in available:
                findings.append(Finding(
                    fd.rel_path, name, 0, "all_phantom",
                    detail="listed in __all__ but not defined or imported",
                ))

    return findings


def check_dupes(files: list[FileData]) -> list[Finding]:
    """
    Flag public names defined more than once:
    - Same-file dupes (two definitions in one file) — always a bug, reported as ERROR
    - Cross-file dupes where both are in the same sub-package — likely unintentional
    Cross-package name sharing (e.g. forms.CharField vs orm.CharField) is expected and skipped.
    """
    from collections import defaultdict

    # Build per-name location list: (rel_path, line)
    name_to_locs: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for fd in files:
        for sym in fd.symbols:
            name_to_locs[sym.name].append((sym.rel_path, sym.line))

    findings: list[Finding] = []
    for name, locations in name_to_locs.items():
        if len(locations) < 2:
            continue

        # Split into same-file groups and cross-file groups
        paths = [p for p, _ in locations]
        unique_paths = list(dict.fromkeys(paths))  # preserve order, deduplicate

        # Same-file duplicates — always a real bug
        same_file = [
            (p, ln) for p, ln in locations
            if paths.count(p) > 1
        ]
        if same_file:
            first_p, first_ln = same_file[0]
            dupes_str = ", ".join(f"{p}:{ln}" for p, ln in same_file[1:])
            findings.append(Finding(
                first_p, name, first_ln, "dupe",
                detail=f"SAME FILE — defined again at {dupes_str}",
            ))
            continue  # don't also report cross-file for this name

        # Cross-file: only flag when both paths share the same top-level package
        # e.g. buraq/orm/functions.py and buraq/orm/aggregates.py → same package "orm"
        # but buraq/forms/fields.py and buraq/orm/fields.py → different packages (skip)
        def _pkg(path: str) -> str:
            # Return the immediate sub-package under buraq/
            parts = path.split("/")
            return parts[1] if len(parts) > 2 else parts[0]

        pkgs = [_pkg(p) for p in unique_paths]
        if len(set(pkgs)) == 1:
            # All in the same package — flag it
            first_p, first_ln = locations[0]
            others = ", ".join(f"{p}:{ln}" for p, ln in locations[1:])
            findings.append(Finding(
                first_p, name, first_ln, "dupe",
                detail=f"also in: {others}",
            ))

    return sorted(findings, key=lambda f: (f.rel_path, f.name))


# ── Renderer ──────────────────────────────────────────────────────────────────

_KIND_COLOR = {
    "doc_gap":     (YELLOW, "⚠ NO DOC    "),
    "all_missing": (ORANGE, "⚠ MISSING   "),
    "all_phantom": (RED,    "✗ PHANTOM   "),
    "dupe":        (CYAN,   "≈ DUPLICATE "),
}

_KIND_LABEL = {
    "doc_gap":     "not referenced in any docs page",
    "all_missing": "public symbol missing from __all__",
    "all_phantom": "__all__ entry has no definition or import",
    "dupe":        "same name defined in multiple files",
}


def _print_findings(findings: list[Finding], show_only_fail: bool) -> None:
    if not findings and show_only_fail:
        return

    by_path: dict[str, list[Finding]] = {}
    for f in findings:
        by_path.setdefault(f.rel_path, []).append(f)

    for path, items in sorted(by_path.items()):
        print(f"\n{BOLD}{CYAN}── {path} ──{RESET}")
        for f in items:
            color, badge = _KIND_COLOR[f.kind]
            loc = f":{f.line}" if f.line else ""
            detail = f"  {RESET}({f.detail})" if f.detail else ""
            print(f"  {color}{badge}{RESET}  {f.name}{loc}{detail}")


def run_audit(
    checks: set[str],
    filter_module: str | None,
    show_only_fail: bool,
    min_len: int,
) -> int:
    files = _collect(min_len, filter_module)
    all_findings: list[Finding] = []

    results: dict[str, list[Finding]] = {}

    if "docs" in checks:
        results["docs"] = check_docs(files)
        all_findings.extend(results["docs"])

    if "exports" in checks:
        results["exports"] = check_exports(files)
        all_findings.extend(results["exports"])

    if "dupes" in checks:
        results["dupes"] = check_dupes(files)
        all_findings.extend(results["dupes"])

    if not show_only_fail:
        # Show all symbols with their status
        doc_texts: list[tuple[str, str]] = []
        if "docs" in checks:
            for df in _doc_files():
                try:
                    doc_texts.append((
                        df.relative_to(ROOT).as_posix(),
                        df.read_text(encoding="utf-8", errors="ignore"),
                    ))
                except Exception:
                    pass

        finding_keys = {(f.rel_path, f.name) for f in all_findings}
        current_mod = None

        for fd in files:
            for sym in fd.symbols:
                is_fail = (sym.rel_path, sym.name) in finding_keys
                if sym.rel_path != current_mod:
                    current_mod = sym.rel_path
                    print(f"\n{BOLD}{CYAN}── {sym.rel_path} ──{RESET}")

                if is_fail:
                    sym_findings = [
                        f for f in all_findings
                        if f.rel_path == sym.rel_path and f.name == sym.name
                    ]
                    for sf in sym_findings:
                        color, badge = _KIND_COLOR[sf.kind]
                        detail = f"  ({sf.detail})" if sf.detail else ""
                        print(f"  {color}{badge}{RESET}  {sym.name}:{sym.line}{detail}")
                else:
                    tag = f"{GREEN}✓{RESET}"
                    kind_badge = "C" if sym.kind == "class" else "f"
                    note = ""
                    if "docs" in checks and doc_texts:
                        mentioned = [p for p, t in doc_texts if sym.name in t]
                        if mentioned:
                            note = f"  ({', '.join(mentioned[:2])})"
                    print(f"  {tag}  [{kind_badge}] {sym.name}:{sym.line}{note}")
    else:
        _print_findings(all_findings, show_only_fail=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    total_syms = sum(len(fd.symbols) for fd in files)
    print(f"\n{BOLD}{'─'*68}")
    print(f"Public symbols: {total_syms}  |  Checks: {', '.join(sorted(checks))}")

    any_fail = False
    for check_name in ("docs", "exports", "dupes"):
        if check_name not in results:
            continue
        count = len(results[check_name])
        if count:
            color = YELLOW if check_name in ("docs", "exports") else CYAN
            label = _KIND_LABEL.get(
                {"docs": "doc_gap", "exports": "all_missing", "dupes": "dupe"}[check_name],
                check_name,
            )
            print(f"  {color}✗ {check_name:10} {count:4} issue(s)  — {label}{RESET}")
            any_fail = True
        else:
            print(f"  {GREEN}✓ {check_name:10}    0 issues{RESET}")

    if "exports" in results:
        phantoms = [f for f in results["exports"] if f.kind == "all_phantom"]
        missing  = [f for f in results["exports"] if f.kind == "all_missing"]
        if phantoms or missing:
            print(f"    exports detail:  {len(missing)} missing from __all__,  "
                  f"{len(phantoms)} phantom entries in __all__")

    print(f"{'─'*68}{RESET}")
    return 1 if any_fail else 0


# ── Entry point ───────────────────────────────────────────────────────────────

_ALL_CHECKS = {"docs", "exports", "dupes"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Buraq feature audit — fully automatic, no registry"
    )
    parser.add_argument(
        "--fail", action="store_true",
        help="Show only failures",
    )
    parser.add_argument(
        "--check", metavar="NAME", default="all",
        help=(
            "Comma-separated checks to run: docs, exports, dupes, all "
            "(default: all)"
        ),
    )
    parser.add_argument(
        "--no-docs", action="store_true",
        help="Skip doc check (alias for --check exports,dupes)",
    )
    parser.add_argument(
        "--module", metavar="PATH",
        help="Audit only files whose path contains this substring",
    )
    parser.add_argument(
        "--min-len", metavar="N", type=int, default=4,
        help="Skip names shorter than N characters (default: 4)",
    )
    args = parser.parse_args()

    if args.no_docs:
        checks = {"exports", "dupes"}
    elif args.check == "all":
        checks = _ALL_CHECKS
    else:
        checks = {c.strip() for c in args.check.split(",") if c.strip()}
        unknown = checks - _ALL_CHECKS
        if unknown:
            parser.error(f"Unknown check(s): {', '.join(unknown)}. "
                         f"Valid: {', '.join(sorted(_ALL_CHECKS))}")

    sys.exit(run_audit(
        checks=checks,
        filter_module=args.module,
        show_only_fail=args.fail,
        min_len=args.min_len,
    ))


if __name__ == "__main__":
    main()
