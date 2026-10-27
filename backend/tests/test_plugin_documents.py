import copy
import json
import pytest
from unified.application import Application
from test_plugins_resources import env, install, action
from test_application import wait


def document():
    return dict(id="community-tool", version="1.0.0", interface_version=1,
                label="Community tool", category="service-management", driver="commands",
                resource_kind="tool", operations=["run"],
                fields=[dict(name="directory", label="Directory", initial="/opt"),
                        dict(name="identity", label="Identity", initial="fixture"),
                        dict(name="mode", label="Mode", initial="check", choices=["check", "repair"])],
                commands={"run": 'printf "%s" "$UNIFIED_MODE"'})


def test_document_import_install_export_restart_and_update(env):
    cfg, app, c = env
    m = document()
    base = "/api/v1/plugin-documents"
    result = c.post(base + "/validate", json={"manifest": m})
    assert result.status_code == 200
    assert not list(app.plugins.catalog_root.iterdir())
    assert c.post(base, json={"manifest": m}).status_code == 201
    assert not app.plugins.installed() and not app.store.jobs()
    reopened = Application(cfg)
    assert reopened.plugins.export_document(m["id"]) == m
    assert not reopened.registry.services
    exported = c.get("/api/v1/plugins/community-tool/manifest")
    assert exported.status_code == 200 and exported.json() == m
    assert "community-tool-1.0.0.json" in exported.headers["content-disposition"]
    install(c, m["id"])
    resource = c.post("/api/v1/resources", json=dict(name="Test", host="h1", adapter=m["id"], settings={})).json()
    assert wait(c, action(c, resource["id"], "run").json()["id"])["status"] == "success"
    old = app.plugins.manifest(app.plugins.installed()[m["id"]])
    m["version"] = "1.1.0"
    m["commands"]["run"] = "printf updated"
    result = c.post(base + "/validate", json={"manifest": m}).json()
    assert result["installed_version"] == "1.0.0" and result["replaces_version"] == "1.0.0"
    assert c.post(base, json={"manifest": m}).status_code == 201
    assert app.plugins.manifest(app.plugins.installed()[m["id"]]) == old
    assert c.post("/api/v1/plugins/community-tool", json={"action": "update"}).status_code == 200
    assert app.plugins.installed()[m["id"]]["version"] == "1.1.0"
    assert c.post("/api/v1/plugins/community-tool", json={"action": "rollback"}).status_code == 200
    assert app.plugins.manifest(app.plugins.installed()[m["id"]]) == old


def test_import_immutable_conflict_and_failed_preview_preserves_catalog(env):
    _, app, c = env
    m = document()
    assert c.post("/api/v1/plugin-documents", json={"manifest": m}).status_code == 201
    install(c, m["id"])
    changed = copy.deepcopy(m)
    changed["commands"]["run"] = "printf changed"
    for path in ("/plugin-documents", "/plugin-documents/validate"):
        r = c.post("/api/v1" + path, json={"manifest": changed})
        assert r.status_code == 422 and "IMMUTABLE" in r.text
    assert app.plugins.export_document(m["id"]) == m
    assert len(list(app.plugins.catalog_root.rglob("*tmp*"))) == 0


@pytest.mark.parametrize("change", [
    {"id": "../../escape"}, {"version": None}, {"label": []}, {"fields": [None]},
    {"fields": [{"name": "mode", "label": "Mode", "initial": {}}]},
    {"commands": []}, {"commands": {"run": 12}}, {"hosts": "opencode"},
    {"interface_version": True}, {"driver": "python"}, {"dependencies": ["other"]},
    {"operations": ["arbitrary"]}, {"description": "x" * 131073},
    {"installed": {"enabled": True}},
])
def test_invalid_documents_fail_without_catalog_or_activation(env, change):
    _, app, c = env
    m = document() | change
    r = c.post("/api/v1/plugin-documents", json={"manifest": m})
    assert r.status_code == 422, r.text
    assert not list(app.plugins.catalog_root.iterdir())
    assert not app.plugins.installed()


def test_document_routes_require_auth_and_exports_are_clean(env):
    _, app, c = env
    for path in ("/plugin-documents", "/plugin-documents/validate"):
        assert c.post("/api/v1" + path, json={"manifest": document()}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/api/v1/plugins/opencode/manifest", headers={"Authorization": "Bearer wrong"}).status_code == 401
    exported = c.get("/api/v1/plugins/opencode/manifest").json()
    assert "installed" not in exported and "available" not in exported
    assert c.post("/api/v1/plugin-documents", json={"manifest": exported}).status_code == 201
    assert c.get("/api/v1/plugins/not-present/manifest").status_code == 404
