import copy
import asyncio
import threading
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


def test_independent_compose_plugins_persist_capabilities_and_shared_target_lock(env, monkeypatch):
    cfg, app, c = env
    original = c.get('/api/v1/plugins/compose/manifest').json()
    copied = copy.deepcopy(original) | {'id': 'personal-compose', 'label': 'Personal Compose', 'operations': ['refresh', 'restart']}
    copied['fields'][0]['initial'] = '/opt/stacks/fixture'
    assert c.post('/api/v1/plugin-documents', json={'manifest': copied}).status_code == 201
    assert not app.plugins.installed()
    assert c.get('/api/v1/plugins/compose/manifest').json() == original
    install(c, 'compose', 'personal-compose')
    def add(adapter, settings):
        response = c.post('/api/v1/resources', json=dict(name=adapter, host='h1', adapter=adapter, settings=settings))
        assert response.status_code == 201, response.text
        return response.json()
    custom = add('personal-compose', {})
    generic = add('compose', {'compose_dir': '/opt/stacks/fixture/'})
    assert custom['settings']['compose_dir'] == '/opt/stacks/fixture'
    assert action(c, custom['id'], 'stop').status_code == 422
    entered, release = threading.Event(), threading.Event()
    adapter = app.registry.service('personal-compose')
    execute = adapter.execute
    async def held(*args):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(.005)
        return await execute(*args)
    monkeypatch.setattr(adapter, 'execute', held)
    job = action(c, custom['id'], 'restart')
    try:
        assert job.status_code == 202, job.text
        assert entered.wait(5)
        blocked = action(c, generic['id'], 'restart')
        assert blocked.status_code == 409, blocked.text
    finally:
        release.set()
    assert wait(c, job.json()['id'])['status'] == 'success'
    reopened = Application(cfg)
    descriptor = reopened.registry.service('personal-compose').descriptor
    assert descriptor.id == 'personal-compose' and descriptor.operations == ('refresh', 'restart')


@pytest.mark.parametrize('change', [
    {'operations': ['run']}, {'resource_kind': 'package'},
    {'fields': []}, {'fields': [{'name':'directory','label':'Directory'}]},
])
def test_compose_manifest_rejects_unsupported_contract(env, change):
    _, _, c = env
    m = c.get('/api/v1/plugins/compose/manifest').json() | {'id':'custom-compose'} | change
    assert c.post('/api/v1/plugin-documents', json={'manifest':m}).status_code == 422


def test_personal_npm_document_installs_as_independent_extension(env):
    _, app, c = env
    m = c.get('/api/v1/plugins/npm-packages/manifest').json()
    m.update(id='personal-extension', label='Personal extension', resource_kind='extension', package_name='@example/extension', hosts=['opencode'])
    defaults = {'package_name':'@example/extension', 'directory':'/opt/fixture', 'scope':'project'}
    for f in m['fields']:
        f['initial'] = defaults.get(f['name'], f.get('initial',''))
    assert c.post('/api/v1/plugin-documents', json={'manifest':m}).status_code == 201
    assert not app.plugins.installed() and not app.store.jobs()
    install(c, m['id'])
    r = c.post('/api/v1/resources', json=dict(name='Extension', host='h1', adapter=m['id'], settings={}))
    assert r.status_code == 201, r.text
    assert r.json()['kind'] == 'extension'
    job = action(c, r.json()['id'], 'install')
    assert job.status_code == 202, job.text
    assert wait(c, job.json()['id'])['status'] == 'success'


def test_personal_compose_uses_interactive_job_session_in_real_mode(env, monkeypatch):
    from dataclasses import replace
    import unified.application as application_module
    _, app, c = env
    m = c.get('/api/v1/plugins/compose/manifest').json() | {'id':'personal-stack'}
    assert c.post('/api/v1/plugin-documents', json={'manifest':m}).status_code == 201
    install(c, m['id'])
    r = c.post('/api/v1/resources', json=dict(name='Stack', host='h1', adapter=m['id'], settings={'compose_dir':'/opt/fixture'}))
    assert r.status_code == 201, r.text
    calls = []
    async def session(context, host, command):
        calls.append(('session', command))
        await context.log('stdout', 'fixture interactive output\n')
    async def capture(config, host, command):
        calls.append(('capture', command))
        return '{"State":"running","Image":"fixture:1.2.3"}'
    async def forbidden(*args):
        raise AssertionError('Compose must use central interactive job session')
    monkeypatch.setattr(app.sessions, 'execute', session)
    monkeypatch.setattr(application_module, 'capture', capture)
    monkeypatch.setattr(app.registry.service(m['id']), 'execute', forbidden)
    monkeypatch.setattr(app, 'config', replace(app.config, mode='ssh'))
    job = action(c, r.json()['id'], 'restart')
    assert job.status_code == 202, job.text
    assert wait(c, job.json()['id'])['status'] == 'success'
    assert [call[0] for call in calls] == ['session', 'capture']
    assert 'restart' in calls[0][1] and '/opt/fixture' in calls[0][1]


def test_copy_create_only_rejects_remote_and_preview_save_collision(env):
    _, app, c = env
    base = '/api/v1/plugin-documents'
    m = document() | {'id':'opencode', 'version':'9.0.0'}
    for path in (base, base+'/validate'):
        result = c.post(path, json={'manifest':m, 'create_only':True})
        assert result.status_code == 422 and 'PLUGIN_EXISTS' in result.text
    assert not list(app.plugins.catalog_root.iterdir())
    m = document()
    assert c.post(base+'/validate', json={'manifest':m, 'create_only':True}).status_code == 200
    intervening = m | {'version':'2.0.0'}
    assert c.post(base, json={'manifest':intervening}).status_code == 201
    result = c.post(base, json={'manifest':m, 'create_only':True})
    assert result.status_code == 422 and 'PLUGIN_EXISTS' in result.text
    assert app.plugins.export_document(m['id']) == intervening
    # Explicit import remains available for deliberate overrides.
    assert c.post(base, json={'manifest':m}).status_code == 201
    assert not app.plugins.installed()
