import hashlib
import logging
import os
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from buraq.conf import settings
from buraq.contrib.staticfiles.storage import (
    _is_absolute_url,
    _normalize_url_prefix,
)

_log = logging.getLogger(__name__)


class _CachedStaticFiles(StaticFiles):
    """
    StaticFiles with cache headers and pre-compressed variants.

    Two things Starlette does not do:

    *Cache-Control* — Starlette sends ETag and Last-Modified, so a browser
    revalidates and gets a 304, but it still makes the request. Cache-Control
    lets it skip that entirely.

    *Pre-compression* — GZipMiddleware compresses every response as it is sent,
    which for a 97 KB stylesheet is ~4.5 ms of CPU per request spent on bytes
    that never change. ``collectstatic`` writes a ``.gz`` beside each compressible
    file, and this serves it when the client accepts it: the same bytes over the
    wire, none of the work.
    """

    #: Encodings this will serve if a matching pre-compressed file exists,
    #: best first. Brotli only appears when collectstatic could produce it.
    _PRECOMPRESSED = ((".br", "br"), (".gz", "gzip"))

    #: Cached for a year and never revalidated. Only correct for a name that
    #: changes when the bytes do.
    _IMMUTABLE_MAX_AGE = 31536000
    #: Long enough to be worth having, short enough that a deploy reaches people.
    _MUTABLE_MAX_AGE = 60

    def __init__(self, *args, max_age: int | None = None, immutable: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.immutable = immutable
        if max_age is None:
            max_age = self._IMMUTABLE_MAX_AGE if immutable else self._MUTABLE_MAX_AGE
        self.max_age = max_age

    def _precompressed(self, full_path, scope) -> tuple[str, str] | None:
        """The best pre-compressed variant the client will take, if one exists."""
        accepted = ""
        for key, value in scope.get("headers", []):
            if key == b"accept-encoding":
                accepted = value.decode("latin-1").lower()
                break
        if not accepted:
            return None

        for suffix, encoding in self._PRECOMPRESSED:
            if encoding not in accepted:
                continue
            candidate = f"{full_path}{suffix}"
            if os.path.isfile(candidate):
                return candidate, encoding
        return None

    def file_response(self, full_path, stat_result, scope, status_code=200):
        variant = self._precompressed(full_path, scope) if status_code == 200 else None
        if variant is not None:
            compressed_path, encoding = variant
            # The media type must come from the *original* name -- a browser
            # asked for a stylesheet, not for application/gzip -- so the type is
            # resolved before swapping in the compressed file.
            media_type = self._guess_type(full_path)
            response = super().file_response(
                compressed_path, os.stat(compressed_path), scope, status_code
            )
            response.headers["Content-Encoding"] = encoding
            if media_type:
                response.headers["Content-Type"] = media_type
            # Caches must key on the encoding, or a gzip response is served to a
            # client that cannot read it.
            response.headers["Vary"] = "Accept-Encoding"
        else:
            response = super().file_response(full_path, stat_result, scope, status_code)

        # `immutable` says "do not revalidate, ever" -- correct only when a
        # changed file arrives under a different URL, which is to say only when
        # the storage hashes names. Sent unconditionally, it meant an edited
        # stylesheet did not reach anyone who had already loaded the old one
        # until their cache entry expired, a year later.
        directive = f"public, max-age={self.max_age}"
        response.headers.setdefault(
            "Cache-Control", f"{directive}, immutable" if self.immutable else directive
        )
        return response

    @staticmethod
    def _guess_type(full_path) -> str | None:
        import mimetypes

        media_type, encoding = mimetypes.guess_type(str(full_path))
        if media_type is None:
            return None
        return f"{media_type}; charset=utf-8" if media_type.startswith("text/") else media_type


def _storage_hashes_names() -> bool:
    """True when collectstatic gives a changed file a new name.

    Only then can a response say ``immutable``: the promise is that this URL will
    never serve different bytes, and a hashed name is what keeps it.
    """
    from buraq.contrib.staticfiles.storage import ManifestStaticFilesStorage, get_storage

    try:
        return isinstance(get_storage(), ManifestStaticFilesStorage)
    except Exception:
        _log.exception("Could not determine the static storage; assuming names are not hashed")
        return False


def _mount_path(url: str) -> str | None:
    """The route path to serve *url* at, or None if there is nothing to mount.

    For an ordinary ``/static/`` this is the setting itself. For an absolute URL
    it is the path component, and the host is dropped: a CDN pull zone fetches
    from this origin on a cache miss, so the files still have to be reachable
    here even though templates point at the CDN. Sites that upload to the CDN
    instead -- a storage zone, an S3 bucket -- set ``SERVE_STATIC = False`` and
    never reach this.

    None when an absolute URL carries no path (``https://cdn.example.com/``),
    since the only thing left to mount at would be ``/``, which would swallow
    every route in the application.
    """
    if _is_absolute_url(url):
        path = urlsplit(url if "://" in url else f"https:{url}").path.rstrip("/")
        return path or None
    return _normalize_url_prefix(url).rstrip("/") or None


class StaticFilesHandler:
    """
    Serves static files — development serves them straight from STATIC_DIR,
    production serves STATIC_ROOT with a far-future Cache-Control header and the
    pre-compressed variants collectstatic wrote.

    Mounts nothing when SERVE_STATIC is off, or when STATIC_URL is absolute:
    both mean the files are served by something that is not this process.
    """

    def __init__(self, app: FastAPI):
        self.app = app
        static_root = getattr(settings, "STATIC_ROOT", None)
        self._static_root = Path(static_root) if static_root else None
        self._static_dir = Path(settings.STATIC_DIR) if settings.STATIC_DIR else Path("static")

    def mount(self) -> None:
        if not getattr(settings, "SERVE_STATIC", True):
            # An API serves no files, and STATIC_DIR = None was no way to say so:
            # it falls back to ./static, which a scaffolded project has.
            return
        if _mount_path(settings.STATIC_URL) is None:
            _log.debug("STATIC_URL (%s) leaves no path to mount; not serving "
                       "static files from this process", settings.STATIC_URL)
        elif settings.DEBUG:
            self._mount_dev()
        else:
            self._mount_production()
        self._mount_media()

    def _dev_directories(self) -> list[str]:
        """Every directory a source file could be in, in search order.

        collectstatic finds files through STATICFILES_DIRS and each installed
        app's static/, but the development mount only ever looked at STATIC_DIR
        -- so a project using the setting the framework itself prefers got its
        files collected in production and a 404 while developing, which reads as
        a missing file rather than a missing mount.
        """
        found: list[str] = []
        for source in (
            *(getattr(settings, "STATICFILES_DIRS", None) or []),
            str(self._static_dir),
        ):
            if source not in found and Path(source).is_dir():
                found.append(source)

        from buraq.contrib.staticfiles.finders import AppDirectoriesFinder

        for _rel, full in AppDirectoriesFinder().list():
            root = str(Path(full).parent)
            if root not in found:
                found.append(root)
        return found

    def _mount_dev(self) -> None:
        directories = self._dev_directories()
        if not directories:
            return
        served = StaticFiles(directory=directories[0])
        # StaticFiles takes one directory but searches all_directories, which is
        # how it serves a package's files alongside a project's.
        served.all_directories = list(directories)
        self.app.mount(_mount_path(settings.STATIC_URL), served, name="static")

    def _mount_production(self) -> None:
        """
        Serve static files with cache headers that let a browser stop asking.

        This used to mount WhiteNoise, which cannot work: WhiteNoise is WSGI
        (``__call__(environ, start_response)``) and mounting it in an ASGI
        application raised TypeError on the first request. Nobody hit it because
        whitenoise was not a dependency, so the ImportError fallback ran instead.

        Compression is not done per request here either: collectstatic writes a
        .gz beside each compressible file and _CachedStaticFiles serves that,
        so the bytes are prepared once rather than on every request.
        """
        root = self._static_root or self._static_dir
        if not Path(root).is_dir():
            return
        self.app.mount(
            _mount_path(settings.STATIC_URL),
            _CachedStaticFiles(
                directory=str(root),
                max_age=getattr(settings, "STATIC_MAX_AGE", None),
                immutable=_storage_hashes_names(),
            ),
            name="static",
        )

    def _mount_media(self) -> None:
        mount_at = _mount_path(settings.MEDIA_URL)
        if mount_at is None:
            _log.debug("MEDIA_URL (%s) leaves no path to mount; not serving "
                       "media from this process", settings.MEDIA_URL)
            return
        media_dir = Path(settings.MEDIA_DIR) if settings.MEDIA_DIR else None
        if media_dir and media_dir.exists():
            self.app.mount(
                mount_at,
                StaticFiles(directory=str(media_dir)),
                name="media",
            )


def collect_static(
    source_dirs: list[str] | None = None,
    dest_dir: str | None = None,
    clear: bool = False,
) -> dict[str, int]:
    """
    Collect static files from all configured sources into STATIC_ROOT.
    Run via: buraq collectstatic

    Uses STATICFILES_FINDERS to discover files and STATICFILES_STORAGE to
    store them (including post-processing such as manifest hashing).

    Returns: {"copied": N, "skipped": N, "post_processed": N}
    """
    from buraq.contrib.staticfiles.storage import get_storage

    storage = get_storage()
    static_root = Path(dest_dir) if dest_dir else Path(storage.location)

    if clear and static_root.exists():
        shutil.rmtree(static_root)

    static_root.mkdir(parents=True, exist_ok=True)

    collected: dict[str, str] = {}
    copied = skipped = 0

    if source_dirs:
        # Legacy / explicit source dirs override finders
        for source in (Path(d) for d in source_dirs):
            if not source.exists():
                continue
            for src_file in source.rglob("*"):
                if not src_file.is_file():
                    continue
                rel = src_file.relative_to(source).as_posix()
                dest_file = static_root / rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                if dest_file.exists() and _file_hash(src_file) == _file_hash(dest_file):
                    skipped += 1
                    continue
                shutil.copy2(src_file, dest_file)
                collected[rel] = str(src_file)
                copied += 1
    else:
        from buraq.contrib.staticfiles.finders import get_files
        for rel, full in get_files():
            dest_file = static_root / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            src_path = Path(full)
            if dest_file.exists() and _file_hash(src_path) == _file_hash(dest_file):
                skipped += 1
                continue
            shutil.copy2(full, dest_file)
            collected[rel] = full
            copied += 1

    post_processed = sum(1 for _ in storage.post_process(collected))

    # Compress once, here, rather than on every request for the life of the
    # deployment. The static handler serves the .gz to any client that accepts
    # it, and GZipMiddleware leaves an already-encoded response alone.
    compressed = _compress_collected(static_root)

    return {
        "copied": copied,
        "skipped": skipped,
        "post_processed": post_processed,
        "compressed": compressed,
    }


def _compress_collected(static_root: Path) -> int:
    """Write a .gz beside every compressible file under ``static_root``."""
    from buraq.contrib.staticfiles.storage import compress_file

    written = 0
    for path in static_root.rglob("*"):
        if path.is_file() and path.suffix != ".gz":
            written += bool(compress_file(str(path)))
    return written


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()
