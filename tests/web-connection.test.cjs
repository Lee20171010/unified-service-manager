const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('web/api.js','utf8').replace(/^export /gm,'');
function client(local=new Map(),session=new Map(),blocked=false) {
  const calls=[];
  const ctx={
    localStorage:{getItem:k=>{if(blocked)throw Error('blocked');return local.get(k)},setItem:(k,v)=>{if(blocked)throw Error('blocked');local.set(k,v)}},
    sessionStorage:{getItem:k=>session.get(k),setItem:(k,v)=>session.set(k,v)},
    AbortSignal:{timeout:()=>undefined},
    fetch:async(path,options)=>{calls.push({path,options});return {ok:ctx.ok,status:ctx.ok?200:401,json:async()=>ctx.ok?{mode:'ssh'}:{detail:'invalid'}}},
    ok:true,
  };
  vm.runInNewContext(source+'\nthis.api={getToken,setToken,connectWorkspace,request};',ctx);
  return {ctx,api:ctx.api,calls,local,session};
}
test('successful connection survives a new browser session',async()=>{
  const first=client();
  await first.api.connectWorkspace('saved-token');
  assert.equal(first.calls[0].options.headers.Authorization,'Bearer saved-token');
  const reopened=client(first.local,new Map());
  assert.equal(reopened.api.getToken(),'saved-token');
  await reopened.api.request('/snapshot');
  assert.equal(reopened.calls[0].options.headers.Authorization,'Bearer saved-token');
});
test('invalid replacement does not overwrite last successful connection',async()=>{
  const c=client(new Map([['unified-token','good']]));c.ctx.ok=false;
  await assert.rejects(c.api.connectWorkspace('wrong'),e=>e.status===401);
  assert.equal(c.api.getToken(),'good');assert.equal(c.local.get('unified-token'),'good');
});
test('legacy session credential is available for verification and migration',async()=>{
  const c=client(new Map(),new Map([['unified-token','legacy']]));
  assert.equal(c.api.getToken(),'legacy');assert.equal(c.local.size,0);
  await c.api.connectWorkspace(c.api.getToken());
  assert.equal(c.local.get('unified-token'),'legacy');
});
test('blocked persistent storage still allows current session connection',async()=>{
  const c=client(new Map(),new Map(),true);
  await c.api.connectWorkspace('token');
  assert.equal(c.api.getToken(),'token');assert.equal(c.session.get('unified-token'),'token');
});
