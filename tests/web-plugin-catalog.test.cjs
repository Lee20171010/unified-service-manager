const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const capabilities=import('data:text/javascript;base64,'+fs.readFileSync('web/capabilities.js').toString('base64'));
test('plugin installs and updates pin displayed version and checksum without changing lifecycle requests',async()=>{
  const {pluginActionBody}=await capabilities;
  const p={version:'1.1.0',artifact_checksum:'a'.repeat(64)};
  assert.deepEqual(pluginActionBody(p,'install'),{action:'install',version:'1.1.0',checksum:'a'.repeat(64)});
  assert.deepEqual(pluginActionBody(p,'update'),{action:'update',version:'1.1.0',checksum:'a'.repeat(64)});
  assert.deepEqual(pluginActionBody(p,'disable'),{action:'disable'});
  assert.deepEqual(pluginActionBody({version:'2.0.0'},'install'),{action:'install',version:'2.0.0'});
});
test('catalog renders source and offline status while preserving installation controls',async()=>{
  const {pluginSourceLabel}=await capabilities;
  const app=fs.readFileSync('web/app.js','utf8');
  const code=app.slice(app.indexOf('function plugins()'),app.indexOf('function bindingDetails('));
  const ctx={data:{plugin_catalog:{checked:123,error:'Offline <fixture>'},plugins:[{id:'billion-context',label:'billion-context',category:'package-management',version:'1.1.0',source:'github',description:'fixture',available:true}]},pluginCategory:'',pluginInstalled:'',pluginSourceLabel,head:()=>'',date:()=> 'checked',button:(label,action)=>`<button data-action="${action}">${label}</button>`,esc:v=>String(v??'').replaceAll('<','&lt;').replaceAll('>','&gt;')};
  vm.runInNewContext(code+';this.html=plugins()',ctx);
  assert.match(ctx.html,/檢查插件更新/);assert.match(ctx.html,/GitHub 官方/);
  assert.match(ctx.html,/1\.1\.0/);assert.match(ctx.html,/Install/);
  assert.match(ctx.html,/Offline &lt;fixture&gt;/);assert.doesNotMatch(ctx.html,/<fixture>/);
});
