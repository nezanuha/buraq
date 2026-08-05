"""
File wrapper classes.

``File``         — thin wrapper around any file-like object
``ContentFile``  — in-memory file from raw bytes or str
``UploadedFile`` — represents a file received via HTTP multipart upload
"""
from __future__ import annotations

import io
import os


class File:
    """
    Thin wrapper around a file-like object.

    Usage::

        with open("photo.jpg", "rb") as f:
            wrapped = File(f, name="photo.jpg")
            url = storage.save(wrapped.name, wrapped)
    """

    DEFAULT_CHUNK_SIZE = 64 * 2**10  # 64 KB

    def __init__(self, file, name: str = ""):
        self.file = file
        self.name = name

    @property
    def size(self) -> int:
        if hasattr(self.file, "size"):
            return self.file.size
        pos = self.file.tell()
        self.file.seek(0, os.SEEK_END)
        size = self.file.tell()
        self.file.seek(pos)
        return size

    def read(self, num_bytes: int = -1) -> bytes:
        return self.file.read(num_bytes)

    def seek(self, position: int) -> None:
        self.file.seek(position)

    def tell(self) -> int:
        return self.file.tell()

    def chunks(self, chunk_size: int | None = None):
        self.seek(0)
        chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        while True:
            data = self.read(chunk_size)
            if not data:
                break
            yield data

    def __iter__(self):
        return self.chunks()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if hasattr(self.file, "close"):
            self.file.close()


class ContentFile(File):
    """
    An in-memory file built from raw ``bytes`` or ``str``.

    Usage::

        f = ContentFile(b"<html>Hello</html>", name="index.html")
        storage.save(f.name, f)
    """

    def __init__(self, content: bytes | str, name: str = ""):
        if isinstance(content, str):
            content = content.encode("utf-8")
        super().__init__(io.BytesIO(content), name=name)
        self._size = len(content)

    @property
    def size(self) -> int:
        return self._size

    def open(self, mode: str = "rb"):
        self.seek(0)
        return self


class UploadedFile(File):
    """
    Represents a file received via an HTTP multipart upload.

    Attributes:
        name         — original filename from the browser
        content_type — MIME type reported by the browser
        size         — file size in bytes
        charset      — character set for text files (or None)
    """

    def __init__(
        self,
        file=None,
        name: str | None = None,
        content_type: str | None = None,
        size: int | None = None,
        charset: str | None = None,
    ):
        super().__init__(file or io.BytesIO(), name=name or "")
        self.content_type = content_type
        self._size = size
        self.charset = charset

    @property
    def size(self) -> int:
        if self._size is not None:
            return self._size
        return super().size

    @classmethod
    def from_starlette(cls, upload) -> UploadedFile:
        """Build an UploadedFile from a Starlette ``UploadFile`` object."""
        return cls(
            file=upload.file,
            name=upload.filename,
            content_type=upload.content_type,
        )
