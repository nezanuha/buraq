"""The page a new project shows at ``/`` until it has something of its own.

A freshly scaffolded project has no root route, and without this it answered
``{"detail":"Not Found"}`` -- which reads as a broken install rather than an
empty one. The alternative was for the scaffold to write a placeholder view into
config/urls.py, but a URL configuration is not where views belong, and a
placeholder that has to be deleted is worse than a page that removes itself.

Only ever served with DEBUG on, and only when the project has not routed ``/``.
"""

from __future__ import annotations

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Buraq</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    font: 15px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    background: #fbfbfd; color: #1d1d20;
  }}
  main {{ max-width: 34rem; padding: 2.5rem 1.5rem; }}
  h1 {{ font-size: 1.55rem; margin: 0 0 .4rem; letter-spacing: -.02em; }}
  p {{ margin: 0 0 1.6rem; color: #5b5b66; }}
  ul {{ list-style: none; margin: 0; padding: 0; }}
  li {{ border-top: 1px solid #e7e7ec; }}
  a {{
    display: flex; justify-content: space-between; gap: 1rem;
    padding: .8rem .2rem; color: inherit; text-decoration: none;
  }}
  a:hover {{ color: #4f46e5; }}
  a span {{ color: #8b8b96; font-size: .875rem; }}
  code {{
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: .875em; background: #f0f0f4; padding: .12em .4em; border-radius: 4px;
  }}
  footer {{ margin-top: 2rem; font-size: .8125rem; color: #8b8b96; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #131316; color: #ececf1; }}
    p, a span, footer {{ color: #9b9ba6; }}
    li {{ border-color: #2a2a31; }}
    code {{ background: #232329; }}
    a:hover {{ color: #a5b4fc; }}
  }}
</style>
</head>
<body>
<main>
  <h1>It works.</h1>
  <p>{project} is running. This page is served by Buraq because nothing is
     routed at <code>/</code> yet — route it and this disappears.</p>
  <ul>
    <li><a href="{docs_url}">API documentation<span>{docs_url}</span></a></li>
    <li><a href="/admin">Admin<span>/admin</span></a></li>
    <li><a href="https://buraqproject.com/docs/getting-started/installation">Guides<span>buraqproject.com</span></a></li>
  </ul>
  <footer>Shown only while <code>DEBUG</code> is on.</footer>
</main>
</body>
</html>
"""


def welcome_html(project: str = "Your project", docs_url: str = "/api/docs") -> str:
    """Render the page. Kept separate so it can be asserted on in a test."""
    return _PAGE.format(project=project, docs_url=docs_url)
