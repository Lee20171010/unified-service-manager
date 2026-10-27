"""Source-directory races must not escape the backup boundary or its limits."""

import os
from pathlib import Path
import zipfile

import pytest

from unified import backups


def swap_after_lstat(monkeypatch, name, change):
    original = os.stat
    changed = False

    def stat(path, *args, **kwargs):
        nonlocal changed
        result = original(path, *args, **kwargs)
        if (
            not changed
            and not isinstance(path, int)
            and Path(path).name == name
            and kwargs.get("follow_symlinks") is False
        ):
            changed = True
            change()
        return result

    monkeypatch.setattr(os, "stat", stat)


def test_pack_rejects_file_replaced_with_symlink_after_validation(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    file = source / "config"
    file.write_text("application settings")
    outside = tmp_path / "outside"
    outside.write_text("private fixture marker")

    def change():
        file.unlink()
        file.symlink_to(outside)

    swap_after_lstat(monkeypatch, "config", change)
    with pytest.raises(RuntimeError, match="SOURCE_CHANGED|SYMLINK"):
        backups.pack(source, "Magpie", tmp_path / "archive.zip")


def test_pack_rejects_parent_replaced_with_symlink_after_validation(tmp_path, monkeypatch):
    source = tmp_path / "source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (nested / "config").write_text("application settings")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "config").write_text("private fixture marker")

    def change():
        nested.rename(tmp_path / "original")
        nested.symlink_to(outside, target_is_directory=True)

    swap_after_lstat(monkeypatch, "nested", change)
    with pytest.raises(RuntimeError, match="SOURCE_CHANGED|SYMLINK"):
        backups.pack(source, "Magpie", tmp_path / "archive.zip")


def test_pack_stays_on_opened_root_when_source_path_is_replaced(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "config").write_text("application settings")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "config").write_text("private fixture marker")

    def change():
        source.rename(tmp_path / "original")
        source.symlink_to(outside, target_is_directory=True)

    swap_after_lstat(monkeypatch, "config", change)
    archive = tmp_path / "archive.zip"
    backups.pack(source, "Magpie", archive)
    with zipfile.ZipFile(archive) as packed:
        assert packed.read("payload/config") == b"application settings"


def test_pack_enforces_actual_bytes_when_file_grows_after_size_check(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    file = source / "config"
    file.write_bytes(b"a")
    inode = file.stat().st_ino
    original_stat, original_fstat = os.stat, os.fstat
    counted_stats = 0
    grew = False

    def grow(result):
        nonlocal grew
        if not grew:
            grew = True
            with file.open("ab") as stream:
                stream.write(b"b" * 64)
        return result

    def stat(path, *args, **kwargs):
        nonlocal counted_stats
        result = original_stat(path, *args, **kwargs)
        if result.st_ino == inode and kwargs.get("follow_symlinks", True):
            counted_stats += 1
            if counted_stats == 2:
                grow(result)
        return result

    def fstat(fd):
        result = original_fstat(fd)
        return grow(result) if result.st_ino == inode else result

    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(os, "fstat", fstat)
    monkeypatch.setattr(backups, "MAX_BYTES", 16)
    with pytest.raises(RuntimeError, match="ARCHIVE_LIMIT"):
        backups.pack(source, "Magpie", tmp_path / "archive.zip")
    assert grew


def test_pack_rejects_fifo_replacement_without_waiting_for_writer(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    file = source / "config"
    file.write_text("application settings")

    def change():
        file.unlink()
        os.mkfifo(file)

    swap_after_lstat(monkeypatch, "config", change)
    with pytest.raises(RuntimeError, match="SOURCE_CHANGED|SOURCE_TYPE"):
        backups.pack(source, "Magpie", tmp_path / "archive.zip")


def test_pack_bounds_empty_directory_count(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    for name in ("one", "two", "three"):
        (source / name).mkdir()
    monkeypatch.setattr(backups, "MAX_SOURCE_ENTRIES", 2)
    with pytest.raises(RuntimeError, match="ARCHIVE_LIMIT"):
        backups.pack(source, "Magpie", tmp_path / "archive.zip")


def test_pack_bounds_directory_depth(tmp_path, monkeypatch):
    source = tmp_path / "source"
    (source / "one" / "two" / "three").mkdir(parents=True)
    monkeypatch.setattr(backups, "MAX_SOURCE_DEPTH", 2)
    with pytest.raises(RuntimeError, match="ARCHIVE_LIMIT"):
        backups.pack(source, "Magpie", tmp_path / "archive.zip")
