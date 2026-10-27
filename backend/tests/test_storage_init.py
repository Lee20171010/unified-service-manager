import os
import stat
from unittest.mock import patch

import pytest

from unified.storage_init import initialize, main


def test_empty_root_directory_initialized_once(tmp_path):
    directory = tmp_path / "data"
    directory.mkdir()
    os.chown(directory, 0, 0)
    assert initialize(directory)
    assert (directory.stat().st_uid, directory.stat().st_gid) == (10001, 10001)
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert not initialize(directory)


def test_populated_directory_and_link_targets_preserved(tmp_path):
    directory = tmp_path / "data"
    directory.mkdir()
    marker = directory / "database"
    marker.write_bytes(b"existing database fixture")
    marker.chmod(0o640)
    outside = tmp_path / "outside"
    outside.write_bytes(b"key fixture")
    outside.chmod(0o600)
    (directory / "link").symlink_to(outside)
    before = [(p.stat().st_uid, p.stat().st_gid, p.stat().st_mode) for p in (directory, marker, outside)]
    assert not initialize(directory)
    assert before == [(p.stat().st_uid, p.stat().st_gid, p.stat().st_mode) for p in (directory, marker, outside)]
    assert marker.read_bytes() == b"existing database fixture"
    assert outside.read_bytes() == b"key fixture"


def test_empty_directory_owned_by_another_user_preserved(tmp_path):
    os.chown(tmp_path, 12345, 12345)
    with patch("unified.storage_init.os.fchown") as chown, patch("unified.storage_init.os.fchmod") as chmod:
        assert not initialize(tmp_path)
        chown.assert_not_called()
        chmod.assert_not_called()


def test_reject_directory_symlink(tmp_path):
    (tmp_path / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        initialize(tmp_path / "link")


def test_reject_file(tmp_path):
    file = tmp_path / "file"
    file.touch()
    with pytest.raises(OSError):
        initialize(file)


def test_main_prepares_configured_writable_directories_without_stdout(tmp_path, monkeypatch, capsys):
    data, sources = tmp_path / "data", tmp_path / "sources"
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("SOURCE_DIR", str(sources))
    main()
    assert data.stat().st_uid == sources.stat().st_uid == 10001
    assert capsys.readouterr().out == ""


def test_main_rejects_existing_file_before_server_start(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.write_text("preserve")
    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("SOURCE_DIR", str(tmp_path / "sources"))
    with pytest.raises(FileExistsError):
        main()
    assert data.read_text() == "preserve"
