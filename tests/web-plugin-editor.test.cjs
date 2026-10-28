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
test('Compose and npm builders describe managed operations without shell recipes',async()=>{
  const {pluginManifest,copyPluginDocument}=await modulePromise;
  const common={id:'my-service',label:'Service',version:'1.0.0',author:'',description:''};
  const compose=pluginManifest({...common,driver:'compose',kind:'service',compose_dir:'/opt/example'});
  assert.equal(compose.driver,'compose');assert.equal(compose.fields[0].initial,'/opt/example');
  assert.deepEqual(compose.operations,['refresh','start','stop','restart','upgrade']);
  const npm=pluginManifest({...common,id:'my-package',driver:'npm',kind:'extension',package_name:'@example/tool',scope:'project',npm_directory:'/opt/app',node:'/usr/bin/node',npm:'/usr/lib/npm/npm-cli.js',package_version:'1.2.3',hosts:'opencode, hermes'});
  assert.deepEqual(npm.hosts,['opencode','hermes']);assert.equal(npm.package_name,'@example/tool');assert.equal(npm.fields.find(f=>f.name==='version').initial,'1.2.3');
  assert.equal(npm.version,'1.0.0');assert.equal(npm.category,'package-management');assert.equal(npm.commands,undefined);
  const copied=copyPluginDocument(npm);assert.equal(copied.id,'');assert.deepEqual(copied.fields,npm.fields);
  copied.fields[0].initial='changed';assert.equal(npm.fields[0].initial,'@example/tool');
  assert.throws(()=>pluginManifest({...common,driver:'compose',kind:'tool'}),/Compose/);
  assert.throws(()=>copyPluginDocument({driver:'backup'}),/備份/);
});
