import test from 'node:test';
import assert from 'node:assert/strict';
import {catalog,fresh,available,changePlugin,newJob,tick,sendInput,interrupt,recover,active,sessionFor,closeSession} from '../prototype/next/model.mjs';
const installed=()=>{const s=fresh();changePlugin(s,'opencode','install');return s;};
test('catalog discovery has zero active plugins; explicit installation activates only chosen package',()=>{const s=fresh();assert.equal(catalog.length,12);assert.equal(Object.keys(s.plugins).length,0);assert.throws(()=>newJob(s,{target:'OpenCode',action:'upgrade',plugin:'opencode'}));changePlugin(s,'opencode','install');assert.equal(available(s,'opencode'),true);assert.equal(available(s,'hermes'),false);});
test('upgrade returns to a shell without changing the final job result or log',()=>{
 const s=installed(),j=newJob(s,{target:'OpenCode',service:'s1',action:'upgrade',plugin:'opencode'});
 tick(s,j);tick(s,j);assert.equal(j.status,'waiting');tick(s,j);assert.equal(j.step,2);
 assert.throws(()=>sendInput(s,j.id,'y','old-process'));
 sendInput(s,j.id,'y',j.generation);while(active(j))tick(s,j);
 assert.equal(j.status,'success');assert.equal(sessionFor(j).phase,'shell');
 const before=JSON.stringify(j.logs);sendInput(s,j.id,'pwd',j.generation);
 assert.equal(j.status,'success');assert.equal(JSON.stringify(j.logs),before);
 assert.ok(sessionFor(j).logs.some(l=>l.text==='/srv/review'));
 assert.ok(!JSON.stringify(s).includes('手動排錯輸出'));
 closeSession(j);assert.throws(()=>sendInput(s,j.id,'pwd',j.generation));
});
test('same-target lock and plugin deactivation protect active jobs',()=>{const s=installed(),j=newJob(s,{target:'OpenCode',service:'s1',action:'upgrade',plugin:'opencode'});assert.throws(()=>newJob(s,{target:'OpenCode',service:'s1',action:'restart',plugin:'opencode'}));assert.throws(()=>changePlugin(s,'opencode','disable'));interrupt(j);changePlugin(s,'opencode','disable');assert.equal(available(s,'opencode'),false);assert.equal(s.jobs.length,1);});
test('backup needs separate installed application/storage and configured destination',()=>{const s=fresh();changePlugin(s,'magpie','install');assert.throws(()=>newJob(s,{target:'Magpie',action:'backup',plugin:'magpie'}));changePlugin(s,'webdav','install');assert.throws(()=>newJob(s,{target:'Magpie',action:'backup',plugin:'magpie'}));s.storage={url:'https://example.invalid/'};const j=newJob(s,{target:'Magpie',action:'backup',plugin:'magpie',scenario:'normal'});while(active(j))tick(s,j);assert.equal(s.backups.length,1);changePlugin(s,'magpie','remove');assert.equal(s.backups.length,1);});
test('failed restore does not report success or add a snapshot',()=>{const s=fresh();for(const p of ['magpie','webdav'])changePlugin(s,p,'install');s.storage={};const j=newJob(s,{target:'Magpie',action:'restore',plugin:'magpie',scenario:'fail'});while(active(j))tick(s,j);assert.equal(j.status,'failed');assert.equal(s.backups.length,0);});
test('page restart explicitly interrupts active mock work and never replays it',()=>{const s=installed(),j=newJob(s,{target:'OpenCode',action:'upgrade',plugin:'opencode'});recover(s);assert.equal(j.status,'interrupted');tick(s,j);assert.equal(j.step,0);});
test('a new tool uses generic installed integration and parameters',()=>{const s=fresh();changePlugin(s,'ssh-service','install');const j=newJob(s,{target:'Future tool',service:'new-tool',action:'run',plugin:'ssh-service',parameter:'emulator-review',scenario:'normal'});while(active(j))tick(s,j);assert.equal(j.status,'success');assert.equal(j.parameter,'emulator-review');});
test('one worker keeps another target queued while first job awaits input',()=>{const s=installed(),a=newJob(s,{target:'A',service:'a',action:'upgrade',plugin:'opencode'});tick(s,a);tick(s,a);const b=newJob(s,{target:'B',service:'b',action:'restart',plugin:'opencode'});assert.equal(b.status,'queued');tick(s,b);assert.equal(b.status,'queued');assert.throws(()=>changePlugin(s,'opencode','disable'));interrupt(a);tick(s,b);assert.equal(b.status,'running');while(active(b))tick(s,b);assert.equal(b.status,'success');});

test('input while upgrade is foreground is never interpreted as a shell command',()=>{
 const s=installed(),j=newJob(s,{target:'A',action:'upgrade',plugin:'opencode'});
 sendInput(s,j.id,'pwd',j.generation);assert.equal(sessionFor(j).logs.length,0);
 tick(s,j);tick(s,j);sendInput(s,j.id,'ls',j.generation);
 assert.equal(j.status,'waiting');assert.equal(sessionFor(j).phase,'foreground');
 assert.equal(sessionFor(j).logs.length,0);
});
test('Ctrl+C returns to shell, and shell Ctrl+C does not change the interrupted job',()=>{
 const s=installed(),j=newJob(s,{target:'A',action:'upgrade',plugin:'opencode'});interrupt(j);
 assert.equal(j.status,'interrupted');assert.equal(sessionFor(j).phase,'shell');
 const before=JSON.stringify(j.logs);interrupt(j);sendInput(s,j.id,'cd logs',j.generation);sendInput(s,j.id,'pwd',j.generation);
 assert.equal(sessionFor(j).cwd,'/srv/review/logs');assert.equal(JSON.stringify(j.logs),before);
 sendInput(s,j.id,'exit',j.generation);assert.equal(sessionFor(j).phase,'closed');
 assert.throws(()=>sendInput(s,j.id,'pwd',j.generation));assert.equal(j.status,'interrupted');
});
test('failed upgrade returns a usable shell; later diagnostics leave failure intact',()=>{
 const s=installed(),j=newJob(s,{target:'A',action:'upgrade',plugin:'opencode',scenario:'fail'});
 while(active(j))tick(s,j);assert.equal(j.status,'failed');assert.equal(sessionFor(j).phase,'shell');
 sendInput(s,j.id,'journalctl',j.generation);assert.equal(j.status,'failed');
 assert.ok(sessionFor(j).logs.some(l=>l.text.includes('service: review log')));
});
test('shell is not persisted and reload cannot revive a completed session',()=>{
 const s=installed(),j=newJob(s,{target:'A',action:'upgrade',plugin:'opencode',scenario:'normal'});
 while(active(j))tick(s,j);sendInput(s,j.id,'echo ephemeral-only',j.generation);
 assert.ok(!JSON.stringify(s).includes('ephemeral-only'));recover(s);
 assert.equal(sessionFor(j),null);assert.equal(j.status,'success');
 assert.throws(()=>sendInput(s,j.id,'pwd',j.generation));
});
test('closing a foreground shell requires interrupt; queued input is rejected',()=>{
 const s=installed(),j=newJob(s,{target:'A',service:'a',action:'upgrade',plugin:'opencode'});
 assert.throws(()=>closeSession(j));const queued=newJob(s,{target:'B',service:'b',action:'upgrade',plugin:'opencode'});
 assert.throws(()=>sendInput(s,queued.id,'pwd',queued.generation));
});
