import asyncio
import sqlite3
from dataclasses import replace

import pytest

from unified.application import Application
from unified.config import Config, DEMO_TOKEN
from unified.store import Store


def test_database_connections_close_and_failed_transactions_rollback(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    with store.connect() as connection:
        connection.execute("INSERT INTO metadata VALUES ('committed', 'yes')")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    with pytest.raises(RuntimeError):
        with store.connect() as failed:
            failed.execute("INSERT INTO metadata VALUES ('rolled_back', 'yes')")
            raise RuntimeError("abort")
    with pytest.raises(sqlite3.ProgrammingError):
        failed.execute("SELECT 1")
    with store.connect() as check:
        assert (
            check.execute(
                "SELECT value FROM metadata WHERE key='committed'"
            ).fetchone()[0]
            == "yes"
        )
        assert (
            check.execute(
                "SELECT value FROM metadata WHERE key='rolled_back'"
            ).fetchone()
            is None
        )


@pytest.mark.asyncio
async def test_shutdown_and_restart_require_service_refresh(tmp_path):
    config = Config(mode="demo", token=DEMO_TOKEN, data_dir=tmp_path, demo_delay=10)
    app = Application(config)
    app.change_plugin("compose","install")
    await app.start()
    job = app.submit("restart", "service", "s1")
    for _ in range(100):
        if app.store.job(job["id"])["status"] == "running":
            break
        await asyncio.sleep(0.001)
    assert app.store.job(job["id"])["status"] == "running"
    await app.close()
    assert app.store.job(job["id"])["status"] == "failed"
    assert app.store.get("services", "s1")["status"] == "unknown"

    queued = app.submit("stop", "service", "s2")
    recovered = Application(replace(config, demo_delay=0.001))
    await recovered.start()
    try:
        assert recovered.store.job(queued["id"])["status"] == "failed"
        assert recovered.store.get("services", "s2")["status"] == "unknown"
        assert not any(
            j["status"] in ("queued", "running") for j in recovered.store.jobs()
        )
    finally:
        await recovered.close()
