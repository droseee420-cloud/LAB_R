import hashlib
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from .filetypes import filename_extension, validate_file
from .validation import MAX_FILE_SIZE, MAX_FILES, MAX_TOTAL_SIZE, BriefError


def sync_directory(path: Path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


@dataclass
class StagedFile:
    id: str
    filename: str
    size_bytes: int
    sha256: str
    content_type: str


class FileStorage(Protocol):
    def read(self, key: str) -> BinaryIO: ...
    def delete(self, key: str) -> None: ...
    def stage(self, batch: str, uploads: list) -> list[StagedFile]: ...
    def promote(self, batch: str, lead_id: str) -> None: ...
    def discard(self, batch: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        for name in ("staging", "objects", "trash"):
            (self.root / name).mkdir(parents=True, exist_ok=True, mode=0o700)

    def _batch(self, kind: str, batch: str) -> Path:
        if not re.fullmatch(r"[a-f0-9-]{36}", batch):
            raise ValueError("Invalid storage identifier")
        path = self.root / kind / batch
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError("Invalid storage path")
        return path

    def _object(self, key: str) -> Path:
        if not re.fullmatch(r"objects/[a-f0-9-]{36}/[a-f0-9-]{36}", key):
            raise ValueError("Invalid storage key")
        path = self.root / key
        if any(p.is_symlink() for p in (path, path.parent, path.parent.parent)) or not path.resolve().is_relative_to(self.root):
            raise ValueError("Invalid storage path")
        return path

    def read(self, key: str) -> BinaryIO:
        return self._object(key).open("rb")

    def delete(self, key: str) -> None:
        self._object(key).unlink(missing_ok=True)

    def _trash(self, key: str) -> Path:
        self._object(key)  # Validate identifiers and live path before any filesystem operation.
        path = self.root / "trash" / key.removeprefix("objects/")
        if any(p.is_symlink() for p in (path, path.parent, path.parent.parent)) or not path.resolve().is_relative_to(self.root):
            raise ValueError("Invalid trash path")
        return path

    def quarantine(self, key: str):
        source, target = self._object(key), self._trash(key)
        target.parent.mkdir(exist_ok=True, mode=0o700)
        sync_directory(target.parent.parent)
        if target.exists():
            raise FileExistsError("Pending storage recovery")
        os.rename(source, target)
        sync_directory(source.parent)
        sync_directory(target.parent)

    def recover_object(self, key: str, live: bool):
        source, target = self._trash(key), self._object(key)
        if not source.exists():
            return
        if live:
            if target.exists():
                raise FileExistsError("Conflicting live storage object")
            target.parent.mkdir(exist_ok=True, mode=0o700)
            sync_directory(target.parent.parent)
            os.rename(source, target)
            sync_directory(target.parent)
        else:
            source.unlink()
        sync_directory(source.parent)

    def trash_keys(self):
        directory = self.root / "trash"
        if directory.is_symlink():
            raise ValueError("Invalid trash directory")
        for batch in directory.iterdir():
            self._batch("trash", batch.name)
            if not batch.is_dir():
                raise ValueError("Invalid trash entry")
            for path in batch.iterdir():
                key = f"objects/{batch.name}/{path.name}"
                self._trash(key)
                if not path.is_file():
                    raise ValueError("Invalid trash object")
                yield key

    def stage(self, batch: str, uploads: list) -> list[StagedFile]:
        if len(uploads) > MAX_FILES:
            raise BriefError("Attach no more than 6 files.")
        directory = self._batch("staging", batch)
        directory.mkdir(mode=0o700)
        result, total = [], 0
        for upload in uploads:
            filename_extension(upload.filename or "")
            file_id, size, checksum = str(uuid4()), 0, hashlib.sha256()
            target = directory / file_id
            with target.open("xb") as out:
                os.chmod(target, 0o600)
                while chunk := upload.file.read(64 * 1024):
                    size += len(chunk)
                    total += len(chunk)
                    if size > MAX_FILE_SIZE or total > MAX_TOTAL_SIZE:
                        raise BriefError("Attachments exceed 10 MiB per file or 30 MiB in total.", "file_size", 413)
                    out.write(chunk)
                    checksum.update(chunk)
                if size == 0:
                    raise BriefError("Empty attachments are not accepted.")
                out.flush()
                os.fsync(out.fileno())
            content_type = validate_file(target, upload.filename)
            result.append(StagedFile(file_id, upload.filename, size, checksum.hexdigest(), content_type))
        sync_directory(directory)
        return result

    def promote(self, batch: str, lead_id: str) -> None:
        destination = self._batch("objects", lead_id)
        if destination.exists():
            raise FileExistsError("Storage destination already exists")
        os.rename(self._batch("staging", batch), destination)
        sync_directory(destination.parent)
        sync_directory(self.root / "staging")

    def discard(self, batch: str) -> None:
        path = self._batch("staging", batch)
        if path.exists():
            shutil.rmtree(path)

    def remove_orphan(self, kind: str, batch: str):
        if kind not in {"staging", "objects"}:
            raise ValueError("Invalid storage area")
        shutil.rmtree(self._batch(kind, batch))
