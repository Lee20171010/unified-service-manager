const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const source=fs.readFileSync('web/plugin-editor.js','utf8');
const modulePromise=import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('command plugin form emits reusable fields and only configured operations',async()=>{
  const {commandManifest}=await modulePromise;
  const args={id:' my-tool ',label:'Tool',version:'1.0.0',author:'Dev',description:'Example',directory:'/opt/tool',kind:'tool',cmd_run:'printf "%s" "$UNIFIED_MODE"',cmd_stop:''};
  const m=commandManifest(args,[{name:'mode',label:'Mode',initial:'check',choices:['check','repair'],required:true}]);
  assert.equal(m.id,'my-tool');assert.deepEqual(m.operations,['run']);assert.equal(m.commands.run,args.cmd_run);
  assert.equal(m.fields[2].name,'mode');assert.equal(m.interface_version,1);
  assert.throws(()=>commandManifest({...args,cmd_run:''},[]),/至少/);
});
test('JSON import rejects arrays, malformed and oversized documents',async()=>{
  const {parsePluginDocument}=await modulePromise;
  assert.deepEqual(parsePluginDocument('{"id":"x"}'),{id:'x'});
  for(const value of ['[]','null','bad',JSON.stringify({description:'文'.repeat(44000)})])assert.throws(()=>parsePluginDocument(value));
});
