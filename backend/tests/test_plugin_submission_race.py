"""Legacy submissions and plugin updates share the same Application transaction boundary."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress, contextmanager
import json
import threading

import pytest

from unified.application import Application
from unified.adapters.contracts import ServiceResult
from unified.config import Config, DEMO_TOKEN


@pytest.mark.asyncio
async def test_legacy_submission_binds_and_executes_the_completed_plugin_update(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog"
    path = catalog / "service-management/fixture/plugin.json"
    path.parent.mkdir(parents=True)
    manifest = dict(
        id="fixture", version="1.0.0", interface_version=1, label="Fixture",
        category="service-management", driver="commands", resource_kind="service",
        operations=["restart"], fields=[dict(name="directory", label="Directory", initial="/opt")],
        commands={"restart": "printf version-one"},
    )
    path.write_text(json.dumps(manifest))
    app = Application(Config(mode="demo", token=DEMO_TOKEN, data_dir=tmp_path / "data", plugin_catalog=catalog))
    app.seed()
    app.change_plugin("fixture", "install")
    resource = app.add_service(dict(name="Fixture service", host="h1", adapter="fixture", settings={}))
    manifest.update(version="1.1.0", commands={"restart": "printf version-two"})
    path.write_text(json.dumps(manifest))

    update_paused, allow_update, submission_boundary = (threading.Event() for _ in range(3))
    thread_role = threading.local()
    original_guard = app.guard

    class ObservedGuard:
        def __enter__(self):
            if getattr(thread_role, "submitting", False):
                submission_boundary.set()
            original_guard.acquire()
            return self

        def __exit__(self, *_):
            original_guard.release()

    app.guard = ObservedGuard()
    connect = app.store.connect

    @contextmanager
    def pause_after_busy_check():
        with connect() as db:
            class ObservedConnection:
                def execute(self, sql, *args):
                    result = db.execute(sql, *args)
                    if "WHERE kind='plugins' AND id=?" in sql and not update_paused.is_set():
                        update_paused.set()
                        assert allow_update.wait(10), "Fixture update was not released"
                    return result

                def __getattr__(self, name):
                    return getattr(db, name)

            yield ObservedConnection()

    create_job = app.store.create_job

    def record_submission_boundary(job):
        # Without the guard, the old implementation gets here with an obsolete binding.
        submission_boundary.set()
        return create_job(job)

    monkeypatch.setattr(app.store, "connect", pause_after_busy_check)
    monkeypatch.setattr(app.store, "create_job", record_submission_boundary)

    def legacy_submission():
        thread_role.submitting = True
        return app.submit("restart", "service", resource["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        update = pool.submit(app.change_plugin, "fixture", "update")
        try:
            assert update_paused.wait(5)
            submit = pool.submit(legacy_submission)
            assert submission_boundary.wait(5)
        finally:
            allow_update.set()
        update.result(timeout=5)
        job = submit.result(timeout=5)

    executed = []
    adapter = app.registry.service("fixture")

    async def execute_fixture(*_):
        executed.append(adapter.descriptor.version)
        return ServiceResult("online", "fixture")

    monkeypatch.setattr(adapter, "execute", execute_fixture)
    worker = asyncio.create_task(app.run())
    try:
        async with asyncio.timeout(5):
            while app.store.job(job["id"])["status"] in ("queued", "running"):
                await asyncio.sleep(0.01)
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
    assert app.store.job(job["id"])["status"] == "success"
    assert job["plugin_versions"]["fixture"] == "1.1.0"
    assert executed == [job["plugin_versions"]["fixture"]]
