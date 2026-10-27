"""Versioned, bounded ZIP snapshots of mounted configuration directories."""

import asyncio
from contextlib import suppress
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
import zipfile
from .store import identifier, now
from .adapters import builtins
from .adapters.contracts import JobContext
from .adapters.demo import simulate

MAX_BYTES = 100 * 1024 * 1024
MAX_FILES = 10000
MAX_SOURCE_ENTRIES = 20000
MAX_SOURCE_DEPTH = 64


async def file_operation(function, *args):
    """Drain a filesystem transaction before cancellation can release its job lock."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        with suppress(Exception):
            await task
        raise


def pack(source: Path, client: str, destination: Path):
    total = 0
    files = 0
    visited = 0
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        root = os.open(source, directory_flags)
    except OSError as exc:
        raise RuntimeError("SOURCE_MISSING: 請掛載不含符號連結的應用程式設定目錄") from exc

    def write_directory(archive, directory, parts):
        nonlocal total, files, visited
        if len(parts) > MAX_SOURCE_DEPTH:
            raise RuntimeError("ARCHIVE_LIMIT: 備份來源目錄過深")
        names = []
        with os.scandir(directory) as entries:
            for entry in entries:
                visited += 1
                if visited > MAX_SOURCE_ENTRIES:
                    raise RuntimeError("ARCHIVE_LIMIT: 備份來源項目過多")
                names.append(entry.name)
        for name in sorted(names):
            before = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode):
                raise RuntimeError("SYMLINK_UNSUPPORTED: 備份來源含有符號連結")
            is_directory = stat.S_ISDIR(before.st_mode)
            if not is_directory and not stat.S_ISREG(before.st_mode):
                raise RuntimeError("SOURCE_TYPE: 備份來源只支援一般檔案與目錄")
            flags = (
                directory_flags
                if is_directory
                else os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            )
            fd = os.open(name, flags, dir_fd=directory)
            try:
                current = os.fstat(fd)
                if (before.st_dev, before.st_ino, stat.S_IFMT(before.st_mode)) != (
                    current.st_dev,
                    current.st_ino,
                    stat.S_IFMT(current.st_mode),
                ):
                    raise RuntimeError("SOURCE_CHANGED: 備份來源在讀取期間已變更")
                if is_directory:
                    write_directory(archive, fd, (*parts, name))
                    continue
                files += 1
                if files > MAX_FILES or current.st_size > MAX_BYTES - total:
                    raise RuntimeError(
                        "ARCHIVE_LIMIT: 設定備份上限為 100 MiB / 10000 檔案"
                    )
                entry = zipfile.ZipInfo(
                    "payload/" + "/".join((*parts, name)),
                    time.localtime(current.st_mtime)[:6],
                )
                entry.external_attr = (current.st_mode & 0xFFFF) << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                # Read the verified descriptor; path reopening would reintroduce symlink races.
                with archive.open(entry, "w") as output:
                    while chunk := os.read(fd, min(65536, MAX_BYTES - total + 1)):
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise RuntimeError(
                                "ARCHIVE_LIMIT: 設定備份上限為 100 MiB / 10000 檔案"
                            )
                        output.write(chunk)
            finally:
                os.close(fd)

    try:
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "unified-manifest.json",
                json.dumps({"format": 1, "client": client, "created": now()}),
            )
            try:
                write_directory(archive, root, ())
            except OSError as exc:
                raise RuntimeError(
                    "SOURCE_CHANGED: 備份來源無法安全讀取，請停止寫入後重試"
                ) from exc
    finally:
        os.close(root)


def restore(
    archive_path: Path, destination: Path, client: str, validate_application=None
):
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise RuntimeError("RESTORE_TARGET: 目的地不可為符號連結")
    stage = Path(tempfile.mkdtemp(prefix=".unified-restore-", dir=parent))
    previous = parent / (".unified-previous-" + identifier())
    swapped = False
    try:
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            if (
                len(entries) > MAX_FILES + 1
                or sum(x.file_size for x in entries) > MAX_BYTES
            ):
                raise RuntimeError("ARCHIVE_LIMIT")
            manifest = json.loads(archive.read("unified-manifest.json"))
            if manifest.get("format") != 1 or manifest.get("client") != client:
                raise RuntimeError("ARCHIVE_MISMATCH: 備份格式或來源不符")
            seen = set()
            for entry in entries:
                name = entry.filename
                if name in seen:
                    raise RuntimeError("DUPLICATE_ARCHIVE_ENTRY")
                seen.add(name)
                if name == "unified-manifest.json":
                    continue
                parts = PurePosixPath(name).parts
                if (
                    not parts
                    or parts[0] != "payload"
                    or ".." in parts
                    or "\\" in name
                    or stat.S_ISLNK(entry.external_attr >> 16)
                ):
                    raise RuntimeError("UNSAFE_ARCHIVE_PATH")
                target = stage.joinpath(*parts[1:])
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        if validate_application is not None:
            validate_application(stage)
        if destination.exists():
            os.replace(destination, previous)
        try:
            os.replace(stage, destination)
            swapped = True
        except BaseException:
            if previous.exists():
                os.replace(previous, destination)
            raise
        return str(previous) if previous.exists() else None
    finally:
        if not swapped:
            shutil.rmtree(stage, ignore_errors=True)
        # A previous configuration snapshot is intentionally retained for rollback.


class BackupService:
    """Shared checksum/archive policy around registered application and storage adapters."""

    def __init__(self, config, registry=None):
        self.config = config
        self.registry = registry or builtins(config)
        self.cache = config.data_dir / "archives"
        self.cache.mkdir(exist_ok=True)

    async def create(self, client, context: JobContext):
        app = self.registry.application_for_backup({"client": client})
        storage = self.registry.storage(self.registry.default_storage)
        self.registry.require(app, "backup")
        self.registry.require(storage, "upload")
        self.registry.require(storage, "download")
        storage.validate()
        id = identifier()
        name = f"{app.descriptor.id}-{id}.zip"
        path = self.cache / name
        verify = self.cache / (name + ".verify")
        await context.log("stdout", "Collecting application configuration…\n")
        try:
            await app.prepare("backup", context)
            await file_operation(pack, app.source(self.config), client, path)
            checksum = await digest(path)
            await context.progress(30)
            await context.log(
                "stdout", f"Uploading archive to {storage.descriptor.label}…\n"
            )
            await storage.upload(name, path)
            await context.progress(60)
            await storage.download(name, verify)
            if await digest(verify) != checksum:
                raise RuntimeError("CHECKSUM_MISMATCH")
            await context.log("stdout", "Uploaded archive checksum verified.\n")
            return dict(
                id=id,
                client=client,
                name=name,
                date=now(),
                bytes=path.stat().st_size,
                sha256=checksum,
                application_adapter=app.descriptor.id,
                storage_adapter=storage.descriptor.id,
            )
        finally:
            path.unlink(missing_ok=True)
            verify.unlink(missing_ok=True)

    async def apply(self, backup, context: JobContext):
        app = self.registry.application_for_backup(backup)
        # Legacy catalog entries were always stored on WebDAV.
        storage = self.registry.storage(backup.get("storage_adapter", "webdav"))
        self.registry.require(app, "restore")
        self.registry.require(storage, "download")
        storage.validate()
        path = self.cache / (backup["id"] + ".restore.zip")
        try:
            await context.log(
                "stdout",
                f"Downloading selected archive from {storage.descriptor.label}…\n",
            )
            await storage.download(backup["name"], path)
            if await digest(path) != backup["sha256"]:
                raise RuntimeError("CHECKSUM_MISMATCH: 備份內容與紀錄不一致")
            await context.progress(50)
            await context.log(
                "stdout",
                "Checksum verified. Validating archive and restoring configuration…\n",
            )
            await app.prepare("restore", context)
            previous = await file_operation(
                restore,
                path,
                app.source(self.config),
                backup["client"],
                app.validate_restore,
            )
            await context.log(
                "stdout",
                "Configuration restored. Previous snapshot: "
                + str(previous or "none")
                + "\n",
            )
        finally:
            path.unlink(missing_ok=True)


async def digest(path):
    return await asyncio.to_thread(
        lambda: hashlib.sha256(path.read_bytes()).hexdigest()
    )


class DemoBackups(BackupService):
    """Simulation never invokes application hooks, file operations or storage transports."""

    async def create(self, client, context):
        app = self.registry.application_for_backup({"client": client})
        await simulate(self.config, context)
        return dict(
            id=identifier(),
            client=client,
            name=f"demo-{context.job_id}.zip",
            date=now(),
            bytes=12800,
            sha256="demo",
            application_adapter=app.descriptor.id,
            storage_adapter=self.registry.default_storage,
        )

    async def apply(self, backup, context):
        await simulate(self.config, context)
        await context.log("stdout", "[DEMO] Restored " + backup["name"] + "\n")
