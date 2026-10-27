"""Execute shipped recipes against isolated executables; never contact a real managed host."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from unified.config import Config, DEMO_TOKEN
from unified.application import Application
from unified.plugins import validate_manifest, manifest_bytes
from unified.resources import ResourceAdapter

STUB = r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
root=Path(os.environ['FIXTURE_ROOT'])
state=json.loads((root/'state.json').read_text())
name=Path(sys.argv[0]).name
args=sys.argv[1:]
with (root/'calls.jsonl').open('a') as f: f.write(json.dumps([name,*args])+'\n')
def save(): (root/'state.json').write_text(json.dumps(state))
if name=='systemctl':
    prop=next((a for a in args if a.startswith('--property=')),None)
    if prop: print(state['load'] if prop.endswith('LoadState') else state['active'])
    else:
        action=next(a for a in args if a in ('start','stop','restart'))
        state['active']='inactive' if action=='stop' else 'active';save()
elif name=='npm':
    if args[0]=='view': print(json.dumps(state.get('resolved','2.0.0')))
    elif args[0]=='install':
        if state.get('fail'): sys.exit(17)
        state['version']=args[-1].split('@')[-1];save()
elif name=='apt-get':
    if state.get('fail'): sys.exit(17)
    state['version']='2.0.0';save()
elif name=='sudo':
    os.execv(args[1],args[1:])
elif name=='dpkg-query': print(state['version'])
elif '--help' in args: print('--no-gateway-restart')
elif '--version' in args: print(state['version'])
elif args and args[0] in ('update','upgrade'):
    if state.get('fail'): sys.exit(17)
    state['version']='2.0.0';save()
else: sys.exit(19)
'''

@pytest.fixture
def fixture(tmp_path):
    root=tmp_path / 'host with spaces;literal'
    bin=root/'prefix/bin';bin.mkdir(parents=True)
    state=root/'state.json'
    state.write_text(json.dumps(dict(load='loaded',active='active',version='1.0.0')))
    for name in ('systemctl','npm','apt-get','sudo','dpkg-query','opencode','hermes','chatgpt'):
        p=bin/name;p.write_text(STUB);p.chmod(0o755)
    pkg=root/'prefix/lib/node_modules/@openchamber/web'
    (pkg/'bin').mkdir(parents=True)
    (pkg/'package.json').write_text(json.dumps({'name':'@openchamber/web'}))
    cli=pkg/'bin/openchamber';cli.write_text(STUB);cli.chmod(0o755)
    (bin/'openchamber').symlink_to(cli)
    return root,bin,state

def manifest(name):
    p=Config().plugin_catalog/'service-management'/name/'plugin.json'
    return validate_manifest(json.loads(p.read_text()))

def execute(name, action, fixture, overrides=None):
    root,bin,_=fixture
    adapter=ResourceAdapter(Config(),manifest(name))
    settings=adapter.validate(dict(directory=str(root),binary=str(bin/name),**(overrides or {})))
    env=dict(os.environ,PATH=str(bin)+os.pathsep+os.environ['PATH'],FIXTURE_ROOT=str(root),HOME=str(root))
    return subprocess.run(adapter.command(settings,action),shell=True,executable='/bin/sh',env=env,text=True,capture_output=True,timeout=10)

def calls(fixture):
    p=fixture[0]/'calls.jsonl'
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

@pytest.mark.parametrize('name',['opencode','openchamber','hermes','chatgpt'])
def test_shipped_defaults_manage_one_selected_unit_and_upgrade(name,fixture):
    m=manifest(name)
    assert m['version']=='1.1.0' and all(m['commands'].get(a) for a in m['operations'])
    for action in ('refresh','doctor','stop','start','restart','upgrade'):
        result=execute(name,action,fixture)
        assert result.returncode==0,(name,action,result.stderr,result.stdout)
        if action=='refresh': assert json.loads(result.stdout)==dict(status='online',version='1.0.0')
    result=execute(name,'refresh',fixture)
    assert json.loads(result.stdout)['version']=='2.0.0'
    unit=next(f['initial'] for f in m['fields'] if f['name']=='unit')
    assert all(c[-1]==unit for c in calls(fixture) if c[0]=='systemctl')
    if name=='hermes': assert ['hermes','update','--no-gateway-restart'] in calls(fixture)
    if name=='openchamber':
        installation=next(c for c in calls(fixture) if c[:2]==['npm','install'])
        assert installation[-1]=='@openchamber/web@2.0.0'
        assert installation[installation.index('--prefix')+1]==str(fixture[0]/'prefix')
    if name=='chatgpt': assert ['apt-get','install','--only-upgrade','chatgpt'] in calls(fixture)

@pytest.mark.parametrize('name',['opencode','openchamber','hermes','chatgpt'])
def test_missing_unit_and_failed_update_do_not_start_or_restart(name,fixture):
    state=fixture[2];state.write_text(json.dumps(dict(load='not-found',active='inactive',version='1.0.0')))
    result=execute(name,'upgrade',fixture)
    assert result.returncode!=0 and 'not installed' in result.stderr
    assert all(c[0]=='systemctl' for c in calls(fixture))
    state.write_text(json.dumps(dict(load='loaded',active='active',version='1.0.0',fail=True)))
    result=execute(name,'upgrade',fixture)
    assert result.returncode==17
    assert not any('restart' in c for c in calls(fixture))

@pytest.mark.parametrize('name',['opencode','openchamber','hermes','chatgpt'])
def test_upgrade_preserves_stopped_state(name,fixture):
    fixture[2].write_text(json.dumps(dict(load='loaded',active='inactive',version='1.0.0')))
    assert execute(name,'upgrade',fixture).returncode==0
    assert json.loads(fixture[2].read_text())['active']=='inactive'
    assert not any('restart' in c for c in calls(fixture))

def test_invalid_unit_does_not_run_commands_and_override_is_explicit(fixture):
    result=execute('opencode','start',fixture,{'unit':'opencode*;touch nope.service'})
    assert result.returncode!=0 and not calls(fixture)
    result=execute('opencode','start',fixture,{'cmd_start':'printf custom-operation'})
    assert result.returncode==0 and result.stdout=='custom-operation' and not calls(fixture)

def test_plugin_update_preserves_old_commands_and_fills_new_instance_defaults():
    adapter=ResourceAdapter(Config(),manifest('opencode'))
    old={'directory':'/opt/service','identity':'existing','cmd_restart':'printf legacy'}
    assert 'printf legacy' in adapter.command(old,'restart')
    cmd=adapter.command(old,'refresh')
    assert 'UNIFIED_UNIT=opencode.service' in cmd
    assert 'UNIFIED_BINARY=opencode' in cmd
    assert 'python3 -c' in cmd

def test_retired_factory_templates_in_old_volume_preserve_installed_and_uploaded_copies(tmp_path):
    examples=Path('/app/legacy-plugin-examples')
    if not examples.exists(): examples=Path(__file__).resolve().parents[2]/'examples/plugin-authoring'
    catalog=tmp_path/'catalog'
    src=examples/'ssh-service/plugin.json'
    dest=catalog/'service-management/ssh-service/plugin.json';dest.parent.mkdir(parents=True)
    shutil.copyfile(src,dest)
    cfg=Config(mode='demo',token=DEMO_TOKEN,data_dir=tmp_path/'data',plugin_catalog=catalog)
    app=Application(cfg)
    assert not app.plugins.discover()
    m=json.loads(src.read_text());raw=manifest_bytes(m)
    folder=app.plugins.root/'ssh-service'/'1.0.0';folder.mkdir(parents=True)
    (folder/'plugin.json').write_bytes(raw)
    record=dict(id='ssh-service',version='1.0.0',enabled=True,checksum=hashlib.sha256(raw).hexdigest())
    with app.store.connect() as db:
        db.execute('INSERT INTO entities VALUES (?,?,?)',('plugins','ssh-service',json.dumps(record)))
    assert app.plugins.catalog()[0]['installed']['enabled']
    assert app.plugins.require('ssh-service')==m
    app.plugins.import_document(m)
    assert app.plugins.discover()['ssh-service']==m
