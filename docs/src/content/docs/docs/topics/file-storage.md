---
title: "File Storage"
description: "Buraq provides a pluggable file storage API for saving, reading, and serving uploaded files."
---

Buraq provides a pluggable file storage API for saving, reading, and serving uploaded files.

## Configuration

```python title="config/settings.py"
# Default storage backend (FileSystemStorage if unset)
DEFAULT_FILE_STORAGE = "buraq.core.files.storage.FileSystemStorage"

# Where files are saved on disk
MEDIA_DIR = "/var/www/media"

# URL prefix used to serve those files
MEDIA_URL = "/media/"
```

## default_storage

A lazy singleton that delegates to whatever backend is configured:

```python
from buraq.core.files.storage import default_storage

# Save
name = await default_storage.save("avatars/alice.jpg", content_file)

# Check existence
exists = await default_storage.exists("avatars/alice.jpg")

# Public URL
url = default_storage.url(name)   # → "/media/avatars/alice.jpg"

# Delete
await default_storage.delete(name)

# Size in bytes
size = await default_storage.size(name)

# List a directory
dirs, files = await default_storage.listdir("avatars/")
```

## FileSystemStorage

```python
from buraq.core.files.storage import FileSystemStorage

storage = FileSystemStorage(
    location = "/var/www/media",   # directory on disk
    base_url = "/media/",          # URL prefix
)

name = await storage.save("docs/report.pdf", content_file)
print(storage.url(name))   # → "/media/docs/report.pdf"
```

If a file with the same name already exists, `save()` automatically appends a counter (`report_1.pdf`, `report_2.pdf`, …).

## ContentFile

An in-memory file built from raw bytes or a string — useful in tests and when generating files on the fly.

```python
from buraq.core.files import ContentFile

# From bytes
f = ContentFile(b"<html>Hello</html>", name="index.html")
await storage.save(f.name, f)

# From string (auto-encoded as UTF-8)
f = ContentFile("Hello, World!", name="hello.txt")
```

## UploadedFile

Represents a file received through an HTTP multipart upload.

```python
from buraq.core.files import UploadedFile

# Build from a Starlette UploadFile object
async def upload_avatar(request):
    form  = await request.form()
    upload = form["avatar"]                          # starlette UploadFile
    f     = UploadedFile.from_starlette(upload)     # wrap it
    name  = await default_storage.save(f"avatars/{f.name}", f)
    return JSONResponse({"url": default_storage.url(name)})
```

### Attributes

| Attribute | Description |
|---|---|
| `name` | Original filename from the browser |
| `content_type` | MIME type reported by the browser |
| `size` | File size in bytes |
| `charset` | Character set for text files, or `None` |

## File

Base wrapper around any file-like object:

```python
from buraq.core.files import File

with open("/tmp/data.csv", "rb") as fh:
    f = File(fh, name="data.csv")
    for chunk in f.chunks(chunk_size=64 * 1024):
        process(chunk)
```

## Custom storage backend

Subclass `Storage` and implement the required methods:

```python
from buraq.core.files.storage import Storage
from buraq.exceptions import ValidationError


class S3Storage(Storage):
    def __init__(self, bucket: str):
        self.bucket = bucket

    async def save(self, name: str, content) -> str:
        # upload to S3
        ...
        return name

    async def delete(self, name: str) -> None:
        # delete from S3
        ...

    async def exists(self, name: str) -> bool:
        # head object
        ...

    def url(self, name: str) -> str:
        return f"https://{self.bucket}.s3.amazonaws.com/{name}"

    async def size(self, name: str) -> int:
        ...

    async def listdir(self, path: str) -> tuple[list, list]:
        ...
```

Register it in settings:

```python title="config/settings.py"
DEFAULT_FILE_STORAGE = "myapp.storage.S3Storage"
```

## Path traversal protection

`FileSystemStorage` prevents path traversal attacks automatically.  Any file
name that would resolve outside the configured `location` (for example
`../../etc/passwd`) raises `SuspiciousFileOperation` before any disk I/O:

```python
from buraq.exceptions import SuspiciousFileOperation

try:
    await storage.save("../../etc/passwd", content)
except SuspiciousFileOperation:
    # request rejected — name escapes storage root
    ...
```

The check uses `os.path.realpath()` to resolve symlinks and `..` components, so
symlink-based escapes are also caught.  You do not need to sanitise file names
yourself before passing them to `save()` or `open()` — the storage layer handles
it.
