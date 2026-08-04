import re
from pathlib import Path

# Strips trailing slash from link meta tags (canonical, prev, next)
_LINK_TAG = re.compile(r'(<link rel="(?:canonical|prev|next)" href="[^"]+[^"/])/+">')

# Strips trailing slash from <a href="..."> — requires at least one non-slash char before the slash
_ANCHOR_HREF = re.compile(r'(<a [^>]*href="[^"]+[^"/])/+"')

# Strips trailing slash from search index "location" values
_SEARCH_LOC = re.compile(r'("location":"[^"]+[^"/])/+"')


def _strip(output: str) -> str:
    output = _LINK_TAG.sub(r'\1">', output)
    output = _ANCHOR_HREF.sub(r'\1"', output)
    return output


def on_post_page(output, **_):
    """Strip trailing slash from all internal URLs in content pages."""
    return _strip(output)


def on_post_template(output, **_):
    """Strip trailing slash from all internal URLs in theme templates (e.g. 404.html)."""
    return _strip(output)


def on_post_build(config, **_):
    """Strip trailing slash from location URLs in the search index."""
    index = Path(config["site_dir"]) / "search" / "search_index.json"
    if index.exists():
        index.write_text(
            _SEARCH_LOC.sub(r'\1"', index.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
