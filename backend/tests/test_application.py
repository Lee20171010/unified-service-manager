import time
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient
from unified.api import create_app
from unified.config import Config, DEMO_TOKEN
from unified.store import Store, Conflict


@pytest.fixture
def config(tmp_path):
    return Config(mode="demo", token=DEMO_TOKEN, data_dir=tmp_path, demo_delay=0.01)


@pytest.fixture
def client(config):
    from catalog_fixture import seed_catalog
    api = create_app(config)
    seed_catalog(api.state.application)
    with TestClient(api, headers={"Authorization": "Bearer " + DEMO_TOKEN}) as c:
        for id in ("compose","magpie","serverbox","webdav"):
            assert c.post("/api/v1/plugins/"+id,json={"action":"install"}).status_code==200
        yield c


def wait(client, id):
    for _ in range(200):
        j = client.get("/api/v1/jobs/" + id).json()
        if j["status"] not in ("queued", "running"):
            return j
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_auth_and_validation(client):
    assert (
        client.get(
            "/api/v1/snapshot", headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/info", headers={"Authorization": ""}).status_code == 200
    assert (
        client.post(
            "/api/v1/hosts", json={"name": "bad", "address": "x;touch /tmp/x"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/services",
            json={"name": "bad", "host": "h1", "compose_dir": "/opt/../etc"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/services",
            json={"name": "bad", "host": "missing", "compose_dir": "/opt/app"},
        ).status_code
        == 404
    )


def test_new_host_service_jobs_and_logs(client):
    host = client.post(
        "/api/v1/hosts", json={"name": "new-lab", "address": "192.0.2.5"}
    ).json()
    assert (
        client.post(
            "/api/v1/hosts", json={"name": "new-lab", "address": "192.0.2.6"}
        ).status_code
        == 409
    )
    service = client.post(
        "/api/v1/services",
        json={"name": "paperless", "host": host["id"], "compose_dir": "/opt/paperless"},
    ).json()
    assert (
        client.post(
            "/api/v1/services",
            json={
                "name": "alias",
                "host": host["id"],
                "compose_dir": "/opt/paperless/",
            },
        ).status_code
        == 409
    )
    for action, expected in [
        ("refresh", "online"),
        ("stop", "stopped"),
        ("start", "online"),
        ("restart", "online"),
        ("upgrade", "online"),
    ]:
        response = client.post(
            f"/api/v1/services/{service['id']}/jobs", json={"action": action}
        )
        assert response.status_code == 202
        j = wait(client, response.json()["id"])
        assert j["status"] == "success"
        snapshot = client.get("/api/v1/snapshot").json()
        assert (
            next(s for s in snapshot["services"] if s["id"] == service["id"])["status"]
            == expected
        )
        logs = client.get(f"/api/v1/jobs/{j['id']}/logs").json()
        assert logs and all(l["stream"] == "stdout" for l in logs)
        assert (
            client.get(f"/api/v1/jobs/{j['id']}/logs?after={logs[-1]['seq']}").json()
            == []
        )
        assert "Exit code: 0" in client.get(f"/api/v1/jobs/{j['id']}/log.txt").text


def test_conflict_and_failure(client):
    first = client.post(
        "/api/v1/services/s1/jobs", json={"action": "upgrade", "scenario": "long"}
    ).json()
    assert (
        client.post("/api/v1/services/s1/jobs", json={"action": "stop"}).status_code
        == 409
    )
    assert wait(client, first["id"])["status"] == "success"
    failure = client.post(
        "/api/v1/services/s1/jobs", json={"action": "restart", "scenario": "fail"}
    ).json()
    assert wait(client, failure["id"])["status"] == "failed"
    assert any(
        x["stream"] == "stderr"
        for x in client.get(f"/api/v1/jobs/{failure['id']}/logs").json()
    )


def test_backup_restore_and_confirmation(client):
    for name in ["Magpie", "Flutter ServerBox"]:
        job = client.post("/api/v1/backups", json={"client": name}).json()
        assert wait(client, job["id"])["status"] == "success"
        b = next(
            b
            for b in client.get("/api/v1/snapshot").json()["backups"]
            if b["client"] == name
        )
        assert (
            client.post(
                f"/api/v1/backups/{b['id']}/restore", json={"confirm": False}
            ).status_code
            == 422
        )
        restore = client.post(
            f"/api/v1/backups/{b['id']}/restore", json={"confirm": True}
        ).json()
        assert wait(client, restore["id"])["status"] == "success"


def test_recovery_mode_and_credentials(config):
    app = create_app(config).state.application
    app.store.create_job(dict(id="crashed", target_key="s", status="running", date=0))
    app.store.recover()
    assert app.store.job("crashed")["status"] == "failed"
    assert "SERVER_RESTARTED" in app.store.logs("crashed")[0]["text"]
    with pytest.raises(ValueError):
        create_app(replace(config, mode="ssh"))
    with pytest.raises(RuntimeError):
        create_app(replace(config, mode="ssh", token="x" * 48))


def test_terminal_auth_and_demo(client):
    with client.websocket_connect("/api/v1/hosts/h1/terminal") as ws:
        ws.send_json({"token": DEMO_TOKEN})
        assert "DEMO" in ws.receive_json()["text"]
        ws.send_json({"type": "input", "data": "hostname\n"})
        assert "nas-host" in ws.receive_json()["text"]
    from starlette.websockets import WebSocketDisconnect

    with client.websocket_connect("/api/v1/hosts/h1/terminal") as ws:
        ws.send_json({"token": "wrong"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
