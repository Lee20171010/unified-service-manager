import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import pytest
import httpx
from fastapi.testclient import TestClient
from unified.application import Application
from unified.api import create_app
from unified.config import Config, DEMO_TOKEN
from unified.plugin_catalog import RemoteCatalog, validate_index, BUILTIN_IDS, BASE_URL, INDEX_LIMIT
from unified.plugins import manifest_bytes
from catalog_fixture import seed_catalog, CATALOG, PLUGINS


def app_at(tmp_path):
    return Application(Config(mode='demo', token=DEMO_TOKEN, data_dir=tmp_path))


def test_fresh_instance_has_only_generic_builtins_and_no_installs(tmp_path):
    app = app_at(tmp_path)
    assert set(app.plugins.discover()) == BUILTIN_IDS
    assert all(p['source']=='builtin' for p in app.plugins.catalog())
    assert not app.plugins.installed() and not app.registry.services
    seed_catalog(app)
    assert len(app.plugins.catalog()) == 11
    assert not app.plugins.installed() and not app.registry.services
    p=next(p for p in app.plugins.catalog() if p['id']=='billion-context')
    assert (p['label'],p['version'],p['source']) == ('billion-context','1.1.0','github')
    assert not (app.plugins.remote.root/'downloads').exists()


def test_install_downloads_pinned_package_then_runs_offline_and_reopens(tmp_path):
    app=app_at(tmp_path);seed_catalog(app)
    view=next(p for p in app.plugins.catalog() if p['id']=='opencode')
    calls=[];fetch=app.plugins.remote._fetch
    app.plugins.remote._fetch=lambda path,limit: (calls.append(path),fetch(path,limit))[1]
    record=app.change_plugin('opencode','install',view['version'],view['artifact_checksum'])
    assert len(calls)==1 and calls[0].startswith('packages/opencode/1.1.0-')
    assert record['version']=='1.1.0'
    reopened=app_at(tmp_path)
    def offline(*args): raise OSError('offline')
    reopened.plugins.remote._fetch=offline
    assert reopened.plugins.require('opencode')['version']=='1.1.0'
    assert reopened.refresh_plugin_catalog()['error']
    assert len(reopened.plugins.remote.available())==8
    assert reopened.plugins.export_document('opencode')['id']=='opencode'
    assert 'opencode' in reopened.registry.services


def test_corrupt_download_and_stale_selection_never_activate(tmp_path):
    app=app_at(tmp_path);seed_catalog(app)
    with pytest.raises(ValueError,match='PLUGIN_CHANGED'):
        app.change_plugin('opencode','install','1.0.0')
    with pytest.raises(ValueError,match='PLUGIN_CHANGED'):
        app.change_plugin('opencode','install','1.1.0','0'*64)
    app.plugins.remote._fetch=lambda *args:b'{}'
    with pytest.raises(ValueError,match='PLUGIN_CHECKSUM'):
        app.change_plugin('opencode','install')
    assert not app.plugins.installed() and not app.registry.services


def test_catalog_refresh_never_replaces_installed_or_custom_definitions(tmp_path):
    app=app_at(tmp_path);seed_catalog(app)
    app.change_plugin('opencode','install')
    old=app.plugins.installed()['opencode'];original=app.plugins.require('opencode')
    m=copy.deepcopy(original);m['version']='1.2.0';m['commands']['doctor']='printf fixture'
    raw=manifest_bytes(m);digest=hashlib.sha256(raw).hexdigest()
    index=json.loads((CATALOG/'index.json').read_text())
    entry=next(p for p in index['plugins'] if p['id']=='opencode')
    entry.update(version='1.2.0',sha256=digest)
    def fetch(path,limit):return json.dumps(index).encode() if path=='index.json' else raw
    app.plugins.remote._fetch=fetch
    app.refresh_plugin_catalog()
    assert app.plugins.installed()['opencode']==old
    assert app.plugins.require('opencode')==original
    app.change_plugin('opencode','update','1.2.0',digest)
    assert app.plugins.require('opencode')==m
    app.change_plugin('opencode','rollback')
    assert app.plugins.require('opencode')==original
    m['version']='9.0.0';m['label']='My custom service'
    app.plugins.import_document(m)
    app.refresh_plugin_catalog()
    p=next(p for p in app.plugins.catalog() if p['id']=='opencode')
    assert p['source']=='custom' and p['version']=='9.0.0'
    assert app.plugins.require('opencode')==original


def test_bad_index_preserves_last_good_cache_and_restart(tmp_path):
    app=app_at(tmp_path);seed_catalog(app)
    old=app.plugins.remote.available()
    app.plugins.remote._fetch=lambda *args:b'{"schema_version":1,"plugins":[{"id":"../escape"}]}'
    assert app.refresh_plugin_catalog()['error']
    assert app.plugins.remote.available()==old
    assert app_at(tmp_path).plugins.remote.available()==old


@pytest.mark.parametrize('change',[
    {'id':'../escape'}, {'sha256':'../../x'}, {'version':'../1'},
    {'url':'https://attacker.invalid/package.json'}, {'id':'compose'},
    {'hosts':['../escape']}, {'category':'unknown'}, {'label':''},
])
def test_index_rejects_untrusted_paths_urls_and_metadata(change):
    index=json.loads((CATALOG/'index.json').read_text());index['plugins'][0].update(change)
    with pytest.raises(ValueError):validate_index(index)


def test_old_catalog_volume_does_not_mask_official_but_custom_files_survive(tmp_path):
    legacy=tmp_path/'legacy';path=legacy/'service-management/opencode/plugin.json';path.parent.mkdir(parents=True)
    original=json.loads((PLUGINS/'service-management/opencode/plugin.json').read_text())
    path.write_bytes(manifest_bytes(original))
    app=Application(Config(mode='demo',token=DEMO_TOKEN,data_dir=tmp_path/'data',plugin_catalog=legacy))
    seed_catalog(app)
    p=next(p for p in app.plugins.catalog() if p['id']=='opencode')
    assert p['source']=='github'
    original['label']='Locally modified';path.write_bytes(manifest_bytes(original))
    p=next(p for p in app.plugins.catalog() if p['id']=='opencode')
    assert p['source']=='custom' and p['label']=='Locally modified'
    assert path.exists()


def test_refresh_and_pinned_install_api_require_auth(tmp_path):
    api=create_app(Config(mode='demo',token=DEMO_TOKEN,data_dir=tmp_path));app=api.state.application
    seed_catalog(app)
    with TestClient(api) as c:
        assert c.post('/api/v1/plugin-catalog/refresh',json={}).status_code==401
        headers={'Authorization':'Bearer '+DEMO_TOKEN}
        result=c.post('/api/v1/plugin-catalog/refresh',json={},headers=headers)
        assert result.status_code==200 and result.json()['error'] is None
        view=next(p for p in c.get('/api/v1/snapshot',headers=headers).json()['plugins'] if p['id']=='billion-context')
        assert c.post('/api/v1/plugins/billion-context',headers=headers,json={'action':'install','version':view['version'],'checksum':view['artifact_checksum']}).status_code==200
        assert c.get('/api/v1/plugins/billion-context/manifest',headers=headers).json()['version']=='1.1.0'


def test_generated_packages_match_index_and_manifest_validation(tmp_path):
    app=app_at(tmp_path);seed_catalog(app)
    for id in app.plugins.remote.available():
        app.change_plugin(id,'install')
        assert app.plugins.require(id)['id']==id


def test_http_fetch_is_bounded_and_does_not_follow_redirects(tmp_path,monkeypatch):
    remote=RemoteCatalog(Config(mode='ssh',token='x'*40,data_dir=tmp_path))
    actual=httpx.Client
    seen=[]
    def handler(req):
        seen.append(req)
        return httpx.Response(302,headers={'location':'https://elsewhere.invalid/secrets'})
    def client(**kwargs):
        assert kwargs['follow_redirects'] is False and kwargs['trust_env'] is False
        return actual(transport=httpx.MockTransport(handler),**kwargs)
    monkeypatch.setattr(httpx,'Client',client)
    assert remote.refresh()['error']
    assert len(seen)==1 and str(seen[0].url)==BASE_URL+'index.json'
    assert 'authorization' not in seen[0].headers
    def oversized(req):return httpx.Response(200,content=b'x'*(INDEX_LIMIT+1))
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:actual(transport=httpx.MockTransport(oversized),**kwargs))
    assert remote.refresh()['error'] and not remote.available()


def test_legacy_custom_migration_is_idempotent_and_does_not_overwrite_ui_import(tmp_path):
    legacy=tmp_path/'legacy';path=legacy/'service-management/opencode/plugin.json';path.parent.mkdir(parents=True)
    m=json.loads((PLUGINS/'service-management/opencode/plugin.json').read_text());m['label']='Legacy custom'
    path.write_bytes(manifest_bytes(m))
    cfg=Config(mode='demo',token=DEMO_TOKEN,data_dir=tmp_path/'data',plugin_catalog=legacy)
    app=Application(cfg)
    app.plugins.migrate_legacy();app.plugins.migrate_legacy()
    assert app.plugins.export_document('opencode')==m
    app.plugins.config=replace(cfg,plugin_catalog=tmp_path/'no-mount')
    assert app.plugins.export_document('opencode')==m
    custom=copy.deepcopy(m);custom['version']='2.0.0';custom['label']='UI custom'
    app.plugins.import_document(custom)
    app.plugins.config=cfg;app.plugins.migrate_legacy()
    assert app.plugins.export_document('opencode')==custom
    assert path.read_bytes()==manifest_bytes(m)
    assert not app.plugins.installed()


def test_download_releases_application_lock_and_rechecks_custom_changes(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    app=app_at(tmp_path);seed_catalog(app)
    entered=threading.Event();release=threading.Event();fetch=app.plugins.remote._fetch
    def blocked(path,limit):
        entered.set()
        assert release.wait(5)
        return fetch(path,limit)
    app.plugins.remote._fetch=blocked
    with ThreadPoolExecutor(max_workers=1) as pool:
        task=pool.submit(app.change_plugin,'opencode','install')
        try:
            assert entered.wait(5)
            assert app.guard.acquire(blocking=False), 'GitHub download held application lifecycle lock'
            try:
                m=json.loads((PLUGINS/'service-management/opencode/plugin.json').read_text())
                m['version']='9.0.0';m['label']='Custom during download'
                app.plugin_document('import',m)
            finally:
                app.guard.release()
        finally:
            release.set()
        with pytest.raises(ValueError,match='PLUGIN_CHANGED'):
            task.result(5)
    assert not app.plugins.installed()
    assert app.plugins.export_document('opencode')['version']=='9.0.0'


def test_unreadable_legacy_file_does_not_block_startup(tmp_path,monkeypatch):
    legacy=tmp_path/'legacy';path=legacy/'service-management/private/plugin.json';path.parent.mkdir(parents=True)
    path.write_text('{}')
    original=Path.read_text
    def read(p,*args,**kwargs):
        if p==path:raise PermissionError('private path must not be exposed')
        return original(p,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    api=create_app(Config(mode='demo',token=DEMO_TOKEN,data_dir=tmp_path/'data',plugin_catalog=legacy))
    with TestClient(api,headers={'Authorization':'Bearer '+DEMO_TOKEN}) as c:
        assert c.get('/healthz').status_code==200
        body=c.get('/api/v1/plugins').text
        assert 'unreadable' in body and 'private path' not in body
        assert c.post('/api/v1/plugins/compose',json={'action':'install'}).status_code==200


@pytest.mark.parametrize('later_action',['disable','remove'])
def test_delayed_update_cannot_override_later_lifecycle_decision(tmp_path,later_action):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    app=app_at(tmp_path);seed_catalog(app);app.change_plugin('opencode','install')
    m=app.plugins.require('opencode');m['version']='1.2.0';raw=manifest_bytes(m)
    app.plugins.remote.entries['opencode'].update(version='1.2.0',sha256=hashlib.sha256(raw).hexdigest())
    entered=threading.Event();release=threading.Event()
    def blocked(*args):
        entered.set();assert release.wait(5);return raw
    app.plugins.remote._fetch=blocked
    with ThreadPoolExecutor(max_workers=1) as pool:
        task=pool.submit(app.change_plugin,'opencode','update')
        try:
            assert entered.wait(5)
            app.change_plugin('opencode',later_action)
        finally:release.set()
        with pytest.raises(ValueError,match='PLUGIN_CHANGED'):task.result(5)
    assert app.plugins.installed()['opencode']['enabled'] is False
    assert app.plugins.installed()['opencode']['version']=='1.1.0'


@pytest.mark.asyncio
async def test_metadata_startup_and_shutdown_do_not_delay_worker_cancellation(tmp_path):
    import asyncio
    import threading
    app=Application(Config(mode='ssh',token='x'*40,data_dir=tmp_path))
    entered=threading.Event();release=threading.Event();stopped=asyncio.Event();started=asyncio.Event()
    def fetch(*args):
        entered.set();assert release.wait(5);return (CATALOG/'index.json').read_bytes()
    async def worker():
        started.set()
        try:await asyncio.Event().wait()
        finally:stopped.set()
    app.plugins.remote._fetch=fetch;app.run=worker
    await app.start();await started.wait()
    assert await asyncio.to_thread(entered.wait,2)
    closing=asyncio.create_task(app.close())
    try:await asyncio.wait_for(stopped.wait(),1)
    finally:
        release.set()
        await asyncio.wait_for(closing,3)
    assert app.plugins.remote.status()['count']==8
    assert not app.plugins.installed()
