"""Executable extension example: a read-only service and a configuration app in fixture storage."""

import asyncio
from dataclasses import replace
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unified.api import create_app
from unified.application import Application
from unified.config import Config, DEMO_TOKEN
from unified.adapters import builtins
from unified.adapters.registry import Registry
from unified.adapters.applications import DirectorySnapshot
from unified.adapters.contracts import (
    Descriptor,
    ConfigField,
    ServiceResult,
    JobContext,
    AdapterError,
)
from unified.backups import BackupService
from test_application import wait


class FixtureService:
    descriptor = Descriptor(
        "fixture",
        "service",
        "Fixture read-only service",
        ("refresh",),
        (ConfigField("unit", "Unit name"),),
    )

    def __init__(self):
        self.calls = []

    def validate(self, settings):
        if set(settings) != {"unit"} or not settings["unit"].strip():
            raise ValueError("unit is required")
        return {"unit": settings["unit"].strip()}

    def identity(self, settings):
        return settings["unit"]

    async def execute(self, host, service, action, context):
        self.calls.append((service["settings"], action))
        await context.log("stderr", "fixture diagnostic\n")
        await context.progress(40)
        return ServiceResult("online", "fixture:1")


class FixtureStorage:
    descriptor = Descriptor(
        "fixture-storage", "storage", "Fixture storage", ("upload", "download")
    )

    def __init__(self):
        self.remote = {}

    def validate(self):
        pass

    async def upload(self, name, path):
        self.remote[name] = path.read_bytes()

    async def download(self, name, path):
        path.write_bytes(self.remote[name])


def fixtures(tmp_path):
    cfg = Config(token="x" * 48, data_dir=tmp_path, source_dir=tmp_path / "sources")
    service, storage = FixtureService(), FixtureStorage()
    app = DirectorySnapshot(
        Descriptor("fixture-app", "backup", "Fixture App", ("backup", "restore")),
        "fixture-app",
    )
    return (
        cfg,
        Registry([service], [app], [storage], "fixture-storage"),
        service,
        storage,
    )


def test_registered_extension_runs_through_authenticated_jobs(tmp_path):
    cfg, registry, adapter, _ = fixtures(tmp_path)
    with TestClient(
        create_app(cfg, registry), headers={"Authorization": "Bearer " + cfg.token}
    ) as c:
        assert (
            c.get(
                "/api/v1/adapters", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        catalog = c.get("/api/v1/adapters").json()
        assert catalog["interface_version"] == 1
        assert catalog["adapters"][0]["fields"][0]["name"] == "unit"
        host = c.post(
            "/api/v1/hosts", json={"name": "fixture", "address": "localhost"}
        ).json()
        payload = dict(
            name="test",
            host=host["id"],
            adapter="fixture",
            settings={"unit": "demo-unit"},
        )
        s = c.post("/api/v1/services", json=payload).json()
        assert s["operations"] == ["refresh"]
        assert s["adapter_label"] == "Fixture read-only service"
        assert (
            c.post("/api/v1/services", json=dict(payload, name="alias")).status_code
            == 409
        )
        assert (
            c.post(
                "/api/v1/services", json=dict(payload, adapter="unknown")
            ).status_code
            == 422
        )
        assert (
            c.post("/api/v1/services", json=dict(payload, settings={})).status_code
            == 422
        )
        assert (
            c.post(
                f"/api/v1/services/{s['id']}/jobs", json={"action": "upgrade"}
            ).status_code
            == 422
        )
        assert c.get("/api/v1/snapshot").json()["jobs"] == []
        job = c.post(
            f"/api/v1/services/{s['id']}/jobs", json={"action": "refresh"}
        ).json()
        assert wait(c, job["id"])["status"] == "success"
        assert adapter.calls == [({"unit": "demo-unit"}, "refresh")]
        assert "fixture diagnostic" in c.get(f"/api/v1/jobs/{job['id']}/log.txt").text
        source = cfg.source_dir / "fixture-app"
        source.mkdir(parents=True)
        (source / "config").write_text("original")
        j = c.post("/api/v1/backups", json={"client": "Fixture App"}).json()
        assert wait(c, j["id"])["status"] == "success"
        b = c.get("/api/v1/snapshot").json()["backups"][0]
        assert b["storage_adapter"] == "fixture-storage"
        (source / "config").write_text("changed")
        r = c.post(f"/api/v1/backups/{b['id']}/restore", json={"confirm": True}).json()
        assert wait(c, r["id"])["status"] == "success"
        assert (source / "config").read_text() == "original"


def test_legacy_records_are_read_without_rewriting_and_compose_input_remains_compatible(
    tmp_path,
):
    cfg = Config(mode="demo", token=DEMO_TOKEN, data_dir=tmp_path, demo_delay=0.001)
    app = Application(cfg)
    app.change_plugin("compose","install")
    app.seed()
    legacy = app.store.get("services", "s1")
    assert "adapter" not in legacy
    assert app.snapshot()["services"][0]["adapter"] == "compose"
    assert app.store.get("services", "s1") == legacy
    with TestClient(
        create_app(cfg), headers={"Authorization": "Bearer " + cfg.token}
    ) as c:
        s = c.post(
            "/api/v1/services",
            json={"name": "new", "host": "h1", "compose_dir": "/opt/new/"},
        ).json()
        assert s["settings"] == {"compose_dir": "/opt/new"}
        assert s["compose_dir"] == "/opt/new"
        assert (
            c.post(
                "/api/v1/services",
                json={
                    "name": "bad",
                    "host": "h1",
                    "compose_dir": "/old",
                    "settings": {"compose_dir": "/different"},
                },
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/v1/services",
                json={
                    "name": "bad",
                    "host": "h1",
                    "settings": {"compose_dir": "/a/../b"},
                },
            ).status_code
            == 422
        )
        assert c.post("/api/v1/backups", json={"client": "Unknown"}).status_code == 422


def test_missing_adapter_is_visible_but_not_executable(tmp_path):
    cfg, registry, _, _ = fixtures(tmp_path)
    app = Application(cfg, registry)
    app.store.put(
        "services",
        {
            "id": "s",
            "name": "orphan",
            "host": "h",
            "adapter": "removed",
            "settings": {},
        },
    )
    view = app.snapshot()["services"][0]
    assert view["available"] is False and view["operations"] == []
    with pytest.raises(AdapterError, match="ADAPTER_UNAVAILABLE"):
        app.submit("refresh", "service", "s")
    assert app.store.jobs() == []


@pytest.mark.parametrize(
    "change",
    [
        {"interface_version": 2},
        {"operations": ("shell",)},
        {"id": "../module"},
        {"kind": "storage"},
    ],
)
def test_registry_rejects_unsupported_contracts(tmp_path, change):
    cfg, registry, adapter, storage = fixtures(tmp_path)
    adapter.descriptor = replace(adapter.descriptor, **change)
    with pytest.raises(ValueError):
        Registry([adapter], [], [storage], "fixture-storage")


def test_registry_rejects_duplicates_and_catalog_excludes_credentials(tmp_path):
    cfg, registry, adapter, storage = fixtures(tmp_path)
    with pytest.raises(ValueError):
        Registry([adapter, adapter], [], [storage], "fixture-storage")
    real = builtins(
        replace(
            cfg,
            webdav_url="https://private.invalid/backups",
            webdav_password="secret-password",
        )
    )
    public = str(real.catalog())
    assert "secret-password" not in public and "private.invalid" not in public


@pytest.mark.asyncio
async def test_app_restore_validation_runs_before_replacement(tmp_path):
    cfg, registry, _, storage = fixtures(tmp_path)
    cfg.validate()
    source = cfg.source_dir / "fixture-app"
    source.mkdir(parents=True)
    (source / "config").write_text("backup")

    async def log(*args):
        pass

    context = JobContext("j", "normal", log, log)
    service = BackupService(cfg, registry)
    b = await service.create("Fixture App", context)
    (source / "config").write_text("current")

    class RejectApplication(DirectorySnapshot):
        def validate_restore(self, staged):
            assert (staged / "config").read_text() == "backup"
            raise AdapterError("APP_FORMAT", "unsupported configuration")

    old = registry.application("fixture-app")
    registry.applications["fixture-app"] = RejectApplication(
        old.descriptor, old.directory
    )
    with pytest.raises(AdapterError, match="APP_FORMAT"):
        await service.apply(b, context)
    assert (source / "config").read_text() == "current"
    assert not list(source.parent.glob(".unified-previous-*"))


def test_demo_never_invokes_real_transports_or_backup_hooks(tmp_path, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("real adapter called")

    monkeypatch.setattr("unified.ssh.operate", forbidden)
    monkeypatch.setattr("unified.adapters.webdav.WebDAVStorage.upload", forbidden)
    monkeypatch.setattr("unified.adapters.webdav.WebDAVStorage.download", forbidden)
    monkeypatch.setattr(
        "unified.adapters.applications.DirectorySnapshot.prepare", forbidden
    )
    cfg = Config(mode="demo", token=DEMO_TOKEN, data_dir=tmp_path, demo_delay=0.001)
    with TestClient(
        create_app(cfg), headers={"Authorization": "Bearer " + cfg.token}
    ) as c:
        for id in ("compose","magpie","webdav"):
            assert c.post("/api/v1/plugins/"+id,json={"action":"install"}).status_code==200
        for path, body in [
            ("/services/s1/jobs", {"action": "restart"}),
            ("/backups", {"client": "Magpie"}),
        ]:
            job = c.post("/api/v1" + path, json=body).json()
            assert wait(c, job["id"])["status"] == "success"
        b = c.get("/api/v1/snapshot").json()["backups"][0]
        job = c.post(
            f"/api/v1/backups/{b['id']}/restore", json={"confirm": True}
        ).json()
        assert wait(c, job["id"])["status"] == "success"


@pytest.mark.asyncio
async def test_restore_uses_recorded_storage_after_default_changes(tmp_path):
    cfg, registry, _, original = fixtures(tmp_path)
    cfg.validate()
    source = cfg.source_dir / "fixture-app"
    source.mkdir(parents=True)
    (source / "config").write_text("saved")

    async def noop(*args):
        pass

    service = BackupService(cfg, registry)
    context = JobContext("j", "normal", noop, noop)
    b = await service.create("Fixture App", context)
    replacement = FixtureStorage()
    replacement.descriptor = replace(replacement.descriptor, id="replacement")
    registry.storages["replacement"] = replacement
    registry.default_storage = "replacement"
    (source / "config").write_text("changed")
    await service.apply(b, context)
    assert (source / "config").read_text() == "saved"
    assert replacement.remote == {}


@pytest.mark.asyncio
async def test_worker_rechecks_capabilities_and_releases_failed_target_lock(tmp_path):
    cfg, registry, adapter, _ = fixtures(tmp_path)
    app = Application(cfg, registry)
    await app.start()
    try:
        host = app.add_host(dict(name="fixture", address="localhost"))
        service = app.add_service(
            dict(
                name="fixture",
                host=host["id"],
                adapter="fixture",
                settings={"unit": "demo"},
            )
        )
        job = app.submit("refresh", "service", service["id"])
        # Remove support after submission but before the event loop dispatches the worker.
        adapter.descriptor = replace(adapter.descriptor, operations=())
        for _ in range(100):
            if app.store.job(job["id"])["status"] == "failed":
                break
            await asyncio.sleep(0.005)
        failed = app.store.job(job["id"])
        assert (
            failed["status"] == "failed" and "OPERATION_UNSUPPORTED" in failed["error"]
        )
        assert not adapter.calls
        assert app.store.get("services", service["id"])["status"] == "unknown"
        adapter.descriptor = replace(adapter.descriptor, operations=("refresh",))
        assert app.submit("refresh", "service", service["id"])["status"] == "queued"
    finally:
        await app.close()
