import asyncio
import json
import shlex
from dataclasses import replace
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unified.api import create_app
from unified.application import Application
from unified.config import Config, DEMO_TOKEN
from unified.resources import npm_command, ResourceAdapter
from unified.plugins import validate_manifest
from test_application import wait


@pytest.fixture
def env(tmp_path):
    cfg = Config(mode="demo", token=DEMO_TOKEN, data_dir=tmp_path, demo_delay=0.005)
    api = create_app(cfg)
    with TestClient(api, headers={"Authorization": "Bearer " + DEMO_TOKEN}) as c:
        yield cfg, api.state.application, c


def install(c, *ids):
    for id in ids:
        response = c.post("/api/v1/plugins/" + id, json={"action": "install"})
        assert response.status_code == 200, response.text


def package(
    c,
    adapter="npm-packages",
    name="example",
    directory="/home/unified/.local",
    package="@example/tool",
):
    response = c.post(
        "/api/v1/resources",
        json=dict(
            name=name,
            host="h1",
            adapter=adapter,
            settings=dict(
                package_name=package,
                scope="user",
                directory=directory,
                node="/usr/bin/node",
                npm="/usr/share/nodejs/npm/bin/npm-cli.js",
                version="latest",
            ),
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


def action(c, id, action, **kw):
    return c.post("/api/v1/resources/" + id + "/jobs", json=dict(action=action, **kw))


def test_zero_plugins_and_install_persistence(env):
    cfg, app, c = env
    snap = c.get("/api/v1/snapshot").json()
    assert len(snap["plugins"]) == 11
    assert not {"ssh-service", "ssh-tool"} & {p["id"] for p in snap["plugins"]}
    assert not snap["adapters"]["adapters"]
    assert all(not s["available"] for s in snap["services"])
    legacy = app.store.get("services", "s1")
    assert (
        c.post("/api/v1/services/s1/jobs", json={"action": "start"}).status_code == 422
    )
    install(c, "compose")
    assert app.store.get("services", "s1") == legacy
    assert not app.store.jobs()
    reopened = Application(cfg)
    assert reopened.snapshot()["services"][0]["available"]
    c.post("/api/v1/plugins/compose", json={"action": "disable"})
    assert not c.get("/api/v1/snapshot").json()["services"][0]["available"]
    assert app.store.get("services", "s1") == legacy


def test_package_install_job_scope_and_legacy_subset(env):
    _, app, c = env
    install(c, "npm-packages")
    r = package(c)
    assert not app.store.jobs() and r["kind"] == "package"
    assert r["id"] not in [
        s["id"] for s in c.get("/api/v1/snapshot").json()["services"]
    ]
    assert action(c, r["id"], "start").status_code == 422
    j = action(c, r["id"], "install").json()
    assert j["resolved_version"] == "1.0.0-demo"
    assert wait(c, j["id"])["status"] == "success"
    assert app.store.get("services", r["id"])["version"] == "1.0.0-demo"
    assert action(c, r["id"], "uninstall").status_code == 422
    assert (
        wait(c, action(c, r["id"], "uninstall", confirm=True).json()["id"])["status"]
        == "success"
    )
    assert app.store.get("services", r["id"])["version"] == "absent"


def test_deduplicate_generic_and_dedicated_and_validation(env):
    _, _, c = env
    install(c, "npm-packages", "billion-context")
    r = package(c, package="billion-context")
    body = dict(
        name="alias", host="h1", adapter="billion-context", settings=r["settings"]
    )
    assert c.post("/api/v1/resources", json=body).status_code == 409
    for key, value in [
        ("package_name", "foo;touch /tmp/owned"),
        ("directory", "/tmp/../etc"),
        ("version", "next"),
        ("scope", "managed"),
    ]:
        invalid = dict(body, settings=dict(r["settings"], **{key: value}))
        assert c.post("/api/v1/resources", json=invalid).status_code == 422


def test_binding_locks_uninstall_and_observed_versions(env):
    _, app, c = env
    install(c, "billion-context", "opencode")
    r = package(c, "billion-context", "bili", package="billion-context")
    parent = c.post(
        "/api/v1/resources",
        json=dict(
            name="OpenCode",
            host="h1",
            adapter="opencode",
            settings=dict(
                directory="/opt/app", identity="opencode", cmd_restart="true"
            ),
        ),
    ).json()
    bound = c.post(
        "/api/v1/resources/" + r["id"] + "/bindings",
        json=dict(
            parent=parent["id"],
            register_command="true",
            unregister_command="true",
            verify_command="echo none",
        ),
    )
    assert bound.status_code == 201, bound.text
    b = bound.json()["bindings"][0]
    assert action(c, r["id"], "uninstall", confirm=True).status_code == 422
    assert wait(c, action(c, r["id"], "install").json()["id"])["status"] == "success"
    j = action(c, r["id"], "register", binding=b["id"], scenario="long").json()
    assert action(c, parent["id"], "restart").status_code == 409
    assert (
        c.post("/api/v1/plugins/opencode", json={"action": "disable"}).status_code
        == 422
    )
    assert wait(c, j["id"])["status"] == "success"
    stored = app.store.get("services", r["id"])["bindings"][0]
    assert stored["registered"] and stored["loaded_version"] == "unknown"
    assert (
        wait(
            c,
            action(c, r["id"], "unregister", binding=b["id"], confirm=True).json()[
                "id"
            ],
        )["status"]
        == "success"
    )
    assert (
        wait(c, action(c, r["id"], "verify", binding=b["id"]).json()["id"])["status"]
        == "success"
    )
    assert (
        wait(c, action(c, r["id"], "uninstall", confirm=True).json()["id"])["status"]
        == "success"
    )


def test_failed_upgrade_and_edit_version_policy(env):
    _, app, c = env
    install(c, "npm-packages")
    r = package(c)
    assert wait(c, action(c, r["id"], "install").json()["id"])["status"] == "success"
    body = {k: r[k] for k in ("name", "host", "adapter", "settings")}
    body["settings"]["version"] = "2.0.0"
    assert c.post("/api/v1/resources/" + r["id"], json=body).status_code == 200
    j = action(c, r["id"], "upgrade", scenario="fail").json()
    assert j["resolved_version"] == "2.0.0"
    assert wait(c, j["id"])["status"] == "failed"
    assert app.store.get("services", r["id"])["version"] == "1.0.0-demo"
    assert app.store.get("services", r["id"])["status"] == "unknown"


def test_catalog_dynamic_loading_and_immutable_versions(env, tmp_path):
    cfg, app, c = env
    catalog = tmp_path / "catalog"
    folder = catalog / "service-management" / "custom"
    folder.mkdir(parents=True)
    manifest = dict(
        id="custom",
        version="1.0.0",
        label="Custom",
        interface_version=1,
        driver="commands",
        category="service-management",
        operations=["run"],
        resource_kind="tool",
        fields=[
            dict(name="directory", label="Directory", initial="/tmp"),
            dict(name="identity", label="Identity", initial="tool"),
        ],
        commands={"run": "printf hello"},
    )
    app.plugins.config = replace(cfg, plugin_catalog=catalog)
    (folder / "plugin.json").write_text(json.dumps(manifest))
    assert not app.registry.services
    install(c, "custom")
    r = c.post(
        "/api/v1/resources",
        json=dict(name="Tool", host="h1", adapter="custom", settings={}),
    ).json()
    assert r["kind"] == "tool"
    assert wait(c, action(c, r["id"], "run").json()["id"])["status"] == "success"
    manifest["commands"]["run"] = "printf changed"
    (folder / "plugin.json").write_text(json.dumps(manifest))
    assert (
        c.post("/api/v1/plugins/custom", json={"action": "update"}).status_code == 422
    )
    manifest["version"] = "1.1.0"
    (folder / "plugin.json").write_text(json.dumps(manifest))
    assert (
        c.post("/api/v1/plugins/custom", json={"action": "update"}).status_code == 200
    )
    assert (
        c.post("/api/v1/plugins/custom", json={"action": "rollback"}).json()["version"]
        == "1.0.0"
    )


def test_npm_commands_quote_paths_and_pin_versions():
    s = dict(
        node="/opt/node bin/node",
        npm="/opt/npm-cli.js",
        scope="project",
        directory="/tmp/a'$(touch injected)",
        package_name="@example/tool",
        version="latest",
    )
    args = shlex.split(npm_command(s, "install", "2.3.4"))
    assert args[-1] == "@example/tool@2.3.4"
    assert args[args.index("--prefix") + 1] == s["directory"]
    assert "--global" not in args
    with pytest.raises(ValueError):
        npm_command(s, "upgrade", "latest")


@pytest.mark.asyncio
async def test_real_pty_input_exit_and_transient_shell(tmp_path):
    import asyncssh
    from unified.job_sessions import JobSessions
    from unified.adapters.contracts import JobContext

    key = asyncssh.generate_private_key("ssh-ed25519")
    key.write_private_key(tmp_path / "id_ed25519")
    server_key = asyncssh.generate_private_key("ssh-ed25519")
    received = []

    class Server(asyncssh.SSHServer):
        def begin_auth(self, username):
            return False

    async def process(p):
        if p.command:
            p.stdout.write("Proceed?\n")
            text = await p.stdin.readline()
            received.append(text)
            p.stdout.write("done\n")
            p.exit(0 if text == "yes\n" else 2)
        else:
            p.stdout.write("$ ")
            async for line in p.stdin:
                p.stdout.write("shell reply\n$ ")

    server = await asyncssh.create_server(
        Server, "127.0.0.1", 0, server_host_keys=[server_key], process_factory=process
    )
    port = server.get_port()
    (tmp_path / "known_hosts").write_text(
        f"[127.0.0.1]:{port} " + server_key.export_public_key().decode()
    )
    cfg = Config(mode="ssh", token="x" * 48, ssh_dir=tmp_path, data_dir=tmp_path)
    sessions = JobSessions(cfg)
    host = dict(
        name="fixture",
        address="127.0.0.1",
        port=port,
        username="fixture",
        key="id_ed25519",
    )
    logs = []

    async def log(stream, text):
        logs.append(text)

    async def progress(value):
        pass

    task = asyncio.create_task(
        sessions.execute(
            JobContext("job", "normal", log, progress), host, "fixture-command"
        )
    )
    try:
        for _ in range(200):
            if "Proceed?" in "".join(logs):
                break
            await asyncio.sleep(0.005)
        s = sessions.view("job")
        assert s["phase"] == "running"
        await sessions.input("job", s["generation"], 1, "yes\n")
        await asyncio.wait_for(task, 5)
        assert received == ["yes\n"] and sessions.view("job")["phase"] == "shell"
        durable = list(logs)
        with pytest.raises(ValueError):
            await sessions.input("job", s["generation"], 1, "duplicate\n")
        with pytest.raises(ValueError):
            await sessions.input("job", "stale", 2, "no\n")
        await sessions.input("job", s["generation"], 2, "pwd\n")
        for _ in range(200):
            if "shell reply" in sessions.view("job")["output"]:
                break
            await asyncio.sleep(0.005)
        assert "shell reply" in sessions.view("job")["output"]
        assert logs == durable
        await sessions.input("job", s["generation"], 3, "", close=True)
        with pytest.raises(ValueError):
            await sessions.input("job", s["generation"], 4, "no\n")
    finally:
        await sessions.close()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("registry_result", ['"2.3.4"', '["2.3.4"]'])
async def test_npm_real_transport_uses_pinned_install_and_reads_observed_version(
    tmp_path,
    registry_result,
):
    import asyncssh
    from unified.adapters.contracts import JobContext

    key = asyncssh.generate_private_key("ssh-ed25519")
    key.write_private_key(tmp_path / "id_ed25519")
    server_key = asyncssh.generate_private_key("ssh-ed25519")
    commands = []

    class Server(asyncssh.SSHServer):
        def begin_auth(self, username):
            return False

    async def process(p):
        commands.append(p.command)
        if " view " in p.command:
            p.stdout.write(registry_result + "\n")
        elif " install " in p.command:
            p.stdout.write("fixture npm install\n")
        else:
            p.stdout.write("2.3.4\n")
        p.exit(0)

    server = await asyncssh.create_server(
        Server, "127.0.0.1", 0, server_host_keys=[server_key], process_factory=process
    )
    port = server.get_port()
    (tmp_path / "known_hosts").write_text(
        f"[127.0.0.1]:{port} " + server_key.export_public_key().decode()
    )
    cfg = Config(mode="ssh", token="x" * 48, data_dir=tmp_path, ssh_dir=tmp_path)
    manifest = json.loads(
        (cfg.plugin_catalog / "package-management/npm-packages/plugin.json").read_text()
    )
    adapter = ResourceAdapter(cfg, manifest)
    host = dict(
        name="fixture",
        address="127.0.0.1",
        port=port,
        username="fixture",
        key="id_ed25519",
    )
    settings = adapter.validate(
        dict(
            package_name="@example/cli",
            scope="user",
            directory="/tmp/prefix",
            node="/usr/bin/node",
            npm="/usr/share/nodejs/npm/bin/npm-cli.js",
            version="latest",
        )
    )

    async def noop(*args):
        pass

    try:
        version = await adapter.resolve(host, settings)
        result = await adapter.execute(
            host,
            dict(settings=settings, resolved_version=version),
            "install",
            JobContext("j", "normal", noop, noop),
        )
        assert result.version == "2.3.4" and result.status == "online"
        assert "@example/cli@2.3.4" in commands[1] and "readFileSync" in commands[2]
        (tmp_path / "known_hosts").write_text("")
        with pytest.raises(asyncssh.HostKeyNotVerifiable):
            await adapter.resolve(host, settings)
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value", [[], ["1.2.3", "2.0.0"], [None], ["latest"], {"version": "1.2.3"}]
)
async def test_npm_rejects_ambiguous_or_invalid_registry_version(
    tmp_path, monkeypatch, value
):
    cfg = Config(mode="ssh", token="x" * 48, data_dir=tmp_path)
    manifest = json.loads(
        (cfg.plugin_catalog / "package-management/npm-packages/plugin.json").read_text()
    )
    adapter = ResourceAdapter(cfg, manifest)

    async def captured(*args):
        return json.dumps(value)

    monkeypatch.setattr("unified.resources.capture", captured)
    with pytest.raises(ValueError, match="VERSION_RESOLUTION"):
        await adapter.resolve(
            {},
            dict(
                node="/usr/bin/node",
                npm="/npm.js",
                package_name="example",
                version="latest",
                scope="user",
            ),
        )


def test_demo_session_survives_view_and_raw_input_is_not_durable(env):
    _, app, c = env
    install(c, "npm-packages")
    r = package(c)
    j = action(c, r["id"], "install").json()
    assert wait(c, j["id"])["status"] == "success"
    endpoint = "/api/v1/jobs/" + j["id"] + "/session"
    session = c.get(endpoint).json()
    assert session["phase"] == "shell"
    before = c.get("/api/v1/jobs/" + j["id"] + "/log.txt").text
    result = c.post(
        endpoint, json=dict(generation=session["generation"], sequence=1, data="pwd\n")
    ).json()
    assert "/home/unified" in result["output"]
    assert c.get("/api/v1/jobs/" + j["id"] + "/log.txt").text == before
    assert (
        c.post(
            endpoint,
            json=dict(generation=session["generation"], sequence=1, data="duplicate"),
        ).status_code
        == 422
    )
    assert (
        c.post(
            endpoint,
            json=dict(generation=session["generation"], sequence=2, close=True),
        ).json()["phase"]
        == "closed"
    )


def test_corrupt_plugin_rejected_and_missing_plugin_preserves_records(env):
    _, app, c = env
    install(c, "npm-packages")
    r = package(c)
    installed = app.plugins.installed()["npm-packages"]
    manifest = app.plugins.root / "npm-packages" / installed["version"] / "plugin.json"
    manifest.write_text("{}")
    reopened = Application(app.config)
    assert not reopened.service_view(reopened.store.get("services", r["id"]))[
        "available"
    ]
    assert reopened.store.get("services", r["id"])["name"] == r["name"]


def test_custom_observation_contract():
    from unified.resources import parse_observation

    assert parse_observation("active", "old").status == "online"
    assert parse_observation("inactive", "old").status == "stopped"
    assert parse_observation("unstructured logs", "old").status == "unknown"
    assert (
        parse_observation('{"status":"online","version":"v2"}', "old").version == "v2"
    )
    with pytest.raises(RuntimeError):
        parse_observation('{"status":"invalid"}', "old")


def test_resolution_failure_is_actionable_and_does_not_queue_or_leak(env, monkeypatch):
    _, app, c = env
    install(c, "npm-packages")
    r = package(c)

    async def fail(*args):
        raise OSError("https://user:private-password@registry.test")

    monkeypatch.setattr(app.registry.service("npm-packages"), "resolve", fail)
    response = action(c, r["id"], "install")
    assert response.status_code == 422
    assert (
        "VERSION_RESOLUTION" in response.text
        and "private-password" not in response.text
    )
    assert not app.store.jobs()
