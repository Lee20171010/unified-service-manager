import asyncio
from dataclasses import replace
import hashlib
import json
import zipfile
from pathlib import Path
import asyncssh
import httpx
import pytest
from unified.backups import pack, restore, BackupService
from unified.config import Config
from unified.adapters.contracts import JobContext
from unified.ssh import operate, compose_command, parse_status


@pytest.mark.asyncio
async def test_cancellation_drains_filesystem_transaction():
    import threading
    from unified.backups import file_operation

    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    def operation():
        started.set()
        release.wait(2)
        finished.set()

    task = asyncio.create_task(file_operation(operation))
    await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(0.01)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


def test_archive_roundtrip_and_previous_snapshot(tmp_path):
    source = tmp_path / "magpie"
    source.mkdir()
    (source / "settings.json").write_text('{"theme":"green"}')
    archive = tmp_path / "backup.zip"
    pack(source, "Magpie", archive)
    (source / "settings.json").write_text("changed")
    previous = restore(archive, source, "Magpie")
    assert (source / "settings.json").read_text() == '{"theme":"green"}'
    assert (Path(previous) / "settings.json").read_text() == "changed"


@pytest.mark.parametrize(
    "entry",
    ["../outside", "payload/../../outside", "/tmp/outside", "payload\\..\\outside"],
)
def test_archive_traversal_rejected_without_mutation(tmp_path, entry):
    source = tmp_path / "magpie"
    source.mkdir()
    (source / "keep").write_text("original")
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(
            "unified-manifest.json", json.dumps({"format": 1, "client": "Magpie"})
        )
        z.writestr(entry, "unsafe")
    with pytest.raises(RuntimeError):
        restore(archive, source, "Magpie")
    assert (source / "keep").read_text() == "original"
    assert not (tmp_path / "outside").exists()


def test_wrong_client_and_symlink(tmp_path):
    source = tmp_path / "magpie"
    source.mkdir()
    (source / "settings").write_text("ok")
    archive = tmp_path / "one.zip"
    pack(source, "Magpie", archive)
    with pytest.raises(RuntimeError):
        restore(archive, source, "Flutter ServerBox")
    (source / "link").symlink_to("/etc/passwd")
    with pytest.raises(RuntimeError):
        pack(source, "Magpie", archive)


@pytest.mark.asyncio
async def test_webdav_upload_download_checksum_and_restore(tmp_path, monkeypatch):
    source = tmp_path / "sources" / "magpie"
    source.mkdir(parents=True)
    (source / "settings").write_text("green")
    cfg = Config(
        mode="ssh",
        token="x" * 48,
        data_dir=tmp_path,
        source_dir=tmp_path / "sources",
        webdav_url="https://dav.example/backups",
        webdav_user="u",
        webdav_password="secret",
    )
    remote = {}

    def handle(request):
        assert request.headers.get("Authorization", "").startswith("Basic ")
        if request.method == "PUT":
            remote[str(request.url)] = request.content
            return httpx.Response(201)
        return httpx.Response(200, content=remote[str(request.url)])

    original = httpx.AsyncClient
    monkeypatch.setattr(
        "unified.adapters.webdav.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    lines = []

    async def log(stream, text):
        lines.append(text)

    adapter = BackupService(cfg)

    async def progress(value):
        pass

    context = JobContext("fixture", "normal", log, progress)
    b = await adapter.create("Magpie", context)
    assert b["sha256"] == hashlib.sha256(next(iter(remote.values()))).hexdigest()
    (source / "settings").write_text("changed")
    await adapter.apply(b, context)
    assert (source / "settings").read_text() == "green"
    remote[next(iter(remote))] = b"bad"
    with pytest.raises(RuntimeError, match="CHECKSUM"):
        await adapter.apply(b, context)
    assert (source / "settings").read_text() == "green"


@pytest.mark.asyncio
async def test_real_ssh_transport_host_verification_and_streams(tmp_path):
    key = asyncssh.generate_private_key("ssh-ed25519")
    key.write_private_key(tmp_path / "id_ed25519")
    server_key = asyncssh.generate_private_key("ssh-ed25519")
    commands = []

    class Server(asyncssh.SSHServer):
        def begin_auth(self, username):
            return False

    async def process(p):
        commands.append(p.command)
        if "ps --all" in p.command:
            p.stdout.write(json.dumps([{"State": "running", "Image": "image:1.2"}]))
        else:
            p.stdout.write("starting\n")
            p.stderr.write("diagnostic\n")
        p.exit(0)

    server = await asyncssh.create_server(
        Server, "127.0.0.1", 0, server_host_keys=[server_key], process_factory=process
    )
    port = server.get_port()
    (tmp_path / "known_hosts").write_text(
        f"[127.0.0.1]:{port} " + server_key.export_public_key().decode()
    )
    cfg = Config(token="x" * 48, ssh_dir=tmp_path)
    host = {
        "name": "fixture",
        "address": "127.0.0.1",
        "port": port,
        "username": "fixture",
        "key": "id_ed25519",
    }
    service = {"compose_dir": "/opt/stack with ' quotes"}
    logs = []

    async def log(s, t):
        logs.append((s, t))

    try:
        assert await operate(cfg, service, host, "restart", log) == (
            "online",
            "image:1.2",
        )
        assert any(s == "stderr" for s, t in logs)
        assert "restart" in commands[0]
        (tmp_path / "known_hosts").write_text("")
        with pytest.raises(asyncssh.HostKeyNotVerifiable):
            await operate(cfg, service, host, "stop", log)
    finally:
        server.close()
        await server.wait_closed()


def test_compose_command_allowlist_and_json_formats():
    assert parse_status(
        '{"State":"exited","Image":"a:1"}\n{"State":"running","Image":"a:1"}'
    ) == ("degraded", "a:1")
    assert parse_status("[]")[0] == "stopped"
    with pytest.raises(KeyError):
        compose_command({"compose_dir": "/opt/test"}, "rm -rf /")
