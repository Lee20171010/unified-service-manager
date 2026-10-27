const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const modulePromise = import('data:text/javascript;base64,' + readFileSync(new URL('../web/capabilities.js', `file://${__filename}`)).toString('base64'));
test('operation controls use declared capabilities and ignore unknown verbs', async () => {
  const {serviceActions,canRestore} = await modulePromise;
  assert.deepEqual(serviceActions({operations:['refresh','arbitrary-command']}), ['refresh']);
  assert.deepEqual(serviceActions({}), []);
  assert.equal(canRestore({operations:[]}), false);
  assert.equal(canRestore({operations:['restore']}), true);
});
test('new service and backup types are discovered without a client allowlist', async () => {
  const {serviceAdapters,backupApplications} = await modulePromise;
  const custom = {id:'fixture',kind:'service',interface_version:1,fields:[{name:'unit',label:'Unit'}]};
  assert.deepEqual(serviceAdapters({adapters:{interface_version:1,adapters:[custom]}}), [custom]);
  assert.deepEqual(serviceAdapters({adapters:{interface_version:2,adapters:[custom]}}), []);
  assert.deepEqual(backupApplications({backup_applications:[{client:'New App',operations:['backup']},{client:'Unavailable',operations:[]}]}).map(a => a.client), ['New App']);
});
test('service form serializes adapter fields in their own settings namespace', async () => {
  const {serviceBody} = await modulePromise;
  assert.deepEqual(serviceBody({name:'Demo',host:'h',adapter:'fixture','settings.unit':'demo','settings.port':'word'}),
    {name:'Demo',host:'h',adapter:'fixture',settings:{unit:'demo',port:'word'}});
});
test('package operations are capability driven without service lifecycle controls', async () => {
  const {serviceActions} = await modulePromise;
  assert.deepEqual(serviceActions({operations:['refresh','install','upgrade','uninstall','doctor']}),['refresh','upgrade','install','uninstall','doctor']);
  assert.deepEqual(serviceActions({operations:[]}),[]);
});
