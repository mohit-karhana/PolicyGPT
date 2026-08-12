"""File storage abstraction.

The rest of the app only talks to the `FileStorage` protocol, so swapping
local disk for S3 later means adding one class and changing `get_storage()`
— no changes to routes, services or tasks.
"""

from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import settings


class FileStorage(Protocol):
    def save(self, file: BinaryIO, key: str) -> str:
        """Store the file under `key` and return the path/URI to retrieve it."""
        ...

    def open(self, path: str) -> BinaryIO:
        """Open a previously stored file for reading."""
        ...


class LocalFileStorage:
    """Stores files on the local filesystem under a base directory."""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = Path(base_dir)

    def save(self, file: BinaryIO, key: str) -> str:
        destination = self.base_dir / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "wb") as out:
            while chunk := file.read(1024 * 1024):
                out.write(chunk)
        return str(destination)

    def open(self, path: str) -> BinaryIO:
        return open(path, "rb")


def get_storage() -> FileStorage:
    return LocalFileStorage(settings.upload_dir)
