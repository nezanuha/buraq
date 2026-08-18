"""
Rich debug error page, shown only when DEBUG=True.

Renders a full-page HTML traceback with source context, local variables,
and request info so you can diagnose 500 errors in the browser instead
of hunting through the server console.
"""
from __future__ import annotations

import html
import linecache
import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request


def _short_path(filename: str) -> str:
    """Strip the project root prefix so paths fit on one line."""
    try:
        from pathlib import Path
        return str(Path(filename).resolve().relative_to(Path.cwd()))
    except ValueError:
        return filename


def _source_block(filename: str, lineno: int, context: int = 5) -> list[tuple[int, str, bool]]:
    """Return (line_no, text, is_error_line) tuples around *lineno*."""
    rows = []
    start = max(1, lineno - context)
    end = lineno + context + 1
    for n in range(start, end):
        line = linecache.getline(filename, n)
        if not line:
            continue
        rows.append((n, line.rstrip(), n == lineno))
    return rows


def _extract_frames(exc: BaseException) -> list[dict]:
    frames = []
    tb = exc.__traceback__
    while tb is not None:
        frame = tb.tb_frame
        lineno = tb.tb_lineno
        filename = frame.f_code.co_filename
        funcname = frame.f_code.co_name
        is_project = "site-packages" not in filename

        local_vars = {}
        for k, v in frame.f_locals.items():
            if k.startswith("__"):
                continue
            try:
                local_vars[k] = repr(v)
            except Exception:
                local_vars[k] = "<error calling repr()>"

        frames.append({
            "filename": filename,
            "short": _short_path(filename),
            "lineno": lineno,
            "funcname": funcname,
            "source": _source_block(filename, lineno),
            "locals": local_vars,
            "is_project": is_project,
        })
        tb = tb.tb_next

    return list(reversed(frames))  # most-recent first


def _frames_html(frames: list[dict]) -> str:
    parts = []
    for frame in frames:
        border = "border-error" if frame["is_project"] else "border-neutral"

        # Source code block
        src_rows = ""
        for ln, text, is_err in frame["source"]:
            row_cls = "bg-error text-on-error" if is_err else ""
            marker = "→" if is_err else " "
            src_rows += (
                f'<div class="flex gap-2 px-2 py-px {row_cls}">'
                f'<span class="w-6 shrink-0 text-right select-none text-xs">{ln}</span>'
                f'<span class="shrink-0 select-none">{marker}</span>'
                f'<span>{html.escape(text)}</span>'
                f'</div>'
            )

        source_block = (
            f'<div class="surface surface-1 surface-rounded mt-2 overflow-x-auto">'
            f'<pre class="text-xs py-1">{src_rows}</pre>'
            f'</div>'
        )

        # Local variables
        locals_rows = ""
        for k, v in list(frame["locals"].items())[:30]:
            trunc = v if len(v) <= 300 else v[:300] + "…"
            locals_rows += (
                f'<tr>'
                f'<td class="text-primary font-mono align-top'
                f' pr-3 py-0.5 whitespace-nowrap text-xs">'
                f'{html.escape(k)}</td>'
                f'<td class="font-mono text-xs break-all py-0.5">'
                f'{html.escape(trunc)}</td>'
                f'</tr>'
            )
        locals_block = ""
        if locals_rows:
            open_attr = "open" if frame["is_project"] else ""
            locals_block = (
                f'<details class="mt-2 text-xs" {open_attr}>'
                f'<summary class="cursor-pointer select-none mb-1 font-medium">'
                f'Local variables ({len(frame["locals"])})</summary>'
                f'<div class="surface surface-1 surface-rounded mt-1">'
                f'<table class="w-full"><tbody>{locals_rows}</tbody></table>'
                f'</div>'
                f'</details>'
            )

        parts.append(
            f'<div class="border-l-4 {border} pl-4 mb-5">'
            f'<p class="text-sm">'
            f'File '
            f'<span class="text-accent font-mono">{html.escape(frame["short"])}</span>'
            f', line '
            f'<span class="font-bold">{frame["lineno"]}</span>'
            f', in '
            f'<span class="text-primary font-mono">{html.escape(frame["funcname"])}</span>'
            f'</p>'
            f'{source_block}'
            f'{locals_block}'
            f'</div>'
        )

    return "\n".join(parts)


def render_debug_page(request: Request, exc: BaseException) -> str:
    exc_chain: list[BaseException] = []
    cur: BaseException | None = exc
    while cur is not None:
        exc_chain.append(cur)
        cur = cur.__cause__ or (cur.__context__ if not cur.__suppress_context__ else None)

    root = exc_chain[-1]
    exc_type = html.escape(type(root).__name__)
    exc_msg = html.escape(str(root))

    all_frames_html = _frames_html(_extract_frames(exc))

    chain_notice = ""
    if len(exc_chain) > 1:
        chain_notice = (
            f'<div class="alert alert-soft alert-warning mb-4 text-sm">'
            f'This exception was raised while handling another exception: '
            f'<code>{html.escape(type(exc_chain[0]).__name__)}:'
            f' {html.escape(str(exc_chain[0]))}</code>'
            f'</div>'
        )

    try:
        method = html.escape(request.method)
        url = html.escape(str(request.url))
        query_rows = "".join(
            f'<tr><td class="text-primary pr-4 py-0.5 font-mono text-xs">{html.escape(k)}</td>'
            f'<td class="font-mono text-xs">{html.escape(v)}</td></tr>'
            for k, v in request.query_params.items()
        )
        header_rows = "".join(
            f'<tr><td class="text-primary pr-4 py-0.5 font-mono text-xs">{html.escape(k)}</td>'
            f'<td class="font-mono text-xs break-all">{html.escape(v)}</td></tr>'
            for k, v in sorted(request.headers.items())
            if k.lower() not in ("cookie",)
        )
    except Exception:
        method = "?"
        url = "?"
        query_rows = ""
        header_rows = ""

    query_block = (
        f'<table class="text-sm w-full"><tbody>{query_rows}</tbody></table>'
        if query_rows
        else '<p class="text-sm">None</p>'
    )
    header_block = (
        f'<table class="text-sm w-full"><tbody>{header_rows}</tbody></table>'
        if header_rows
        else '<p class="text-sm">None</p>'
    )

    plain_tb = html.escape("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="darkberry">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{exc_type} — Buraq Debug</title>
  <link rel="stylesheet" href="/_buraq/static/admin/frutjam.min.css">
</head>
<body class="bg-base min-h-screen p-4 md:p-6">
<div class="max-w-5xl mx-auto space-y-4">

  <div class="card bg-error-soft text-on-error-soft border-error">
    <div class="card-content">
      <div class="flex items-start gap-4">
        <span class="text-4xl select-none">🐛</span>
        <div class="min-w-0">
          <h1 class="text-2xl font-bold font-mono">{exc_type}</h1>
          <p class="font-mono text-sm mt-1 break-all">{exc_msg}</p>
          <p class="text-xs mt-2">{method} {url}</p>
        </div>
      </div>
    </div>
  </div>

  {chain_notice}

  <div class="card card-outline">
    <div class="card-content">
      <h2 class="font-bold text-base mb-4">
        Traceback
        <span class="text-xs font-normal ml-2">most recent frame first
        · project frames highlighted</span>
      </h2>
      {all_frames_html}

      <details class="mt-4">
        <summary class="cursor-pointer text-xs select-none font-medium"
        >Copy full traceback</summary>
        <div class="surface surface-1 surface-rounded mt-2">
          <pre class="text-xs p-3 overflow-x-auto whitespace-pre-wrap">{plain_tb}</pre>
        </div>
      </details>
    </div>
  </div>

  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="card card-outline">
      <div class="card-content">
        <h3 class="font-bold mb-3">Query string</h3>
        {query_block}
      </div>
    </div>
    <div class="card card-outline">
      <div class="card-content">
        <h3 class="font-bold mb-3">Request headers</h3>
        {header_block}
      </div>
    </div>
  </div>

  <p class="text-center text-xs pb-4">
    Buraq debug page &mdash; only shown when <code>DEBUG = True</code>
  </p>

</div>
</body>
</html>"""
