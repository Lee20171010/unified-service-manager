const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const commandActions = {refresh:'狀態', start:'啟動', stop:'停止', restart:'重啟', upgrade:'升級', install:'安裝軟體', uninstall:'卸載軟體', doctor:'檢查環境', run:'執行'};
export function commandManifest(values, parameters) {
  const commands = Object.fromEntries(Object.keys(commandActions).filter(a => values['cmd_' + a]?.trim()).map(a => [a, values['cmd_' + a]]));
  if (!Object.keys(commands).length) throw new Error('請至少填寫一項操作命令');
  return {id:values.id.trim(), label:values.label.trim(), version:values.version.trim(), author:values.author.trim(), description:values.description.trim(), interface_version:1, category:['package','extension'].includes(values.kind)?'package-management':'service-management', driver:'commands', resource_kind:values.kind,
    operations:Object.keys(commands), commands,
    fields:[{name:'directory',label:'工作目錄',initial:values.directory.trim(),required:true},{name:'identity',label:'實例名稱',initial:values.id.trim(),required:true}, ...parameters]};
}
export function pluginManifest(values, parameters = []) {
  const driver = values.driver || 'commands';
  const kind = values.kind || 'service';
  if (driver === 'commands') {
    const result = commandManifest(values, parameters);
    if (kind === 'extension') result.hosts = (values.hosts || '').split(',').map(v=>v.trim()).filter(Boolean);
    return result;
  }
  const base = {id:values.id.trim(),label:values.label.trim(),version:values.version.trim(),author:(values.author||'').trim(),description:(values.description||'').trim(),interface_version:1,driver,resource_kind:kind};
  const field = (name,label,initial,choices=[]) => ({name,label,initial,required:true,choices});
  if (driver === 'compose') {
    if (kind !== 'service') throw new Error('Docker Compose 用於常駐服務');
    return {...base, category:'service-management', operations:['refresh','start','stop','restart','upgrade'], fields:[field('compose_dir','Compose 專案目錄',values.compose_dir.trim())]};
  }
  if (driver !== 'npm' || !['package','extension'].includes(kind)) throw new Error('npm 用於套件或擴充插件');
  return {...base,category:'package-management',package_name:values.package_name.trim(),hosts:kind==='extension'?(values.hosts||'').split(',').map(v=>v.trim()).filter(Boolean):[],operations:['refresh','install','upgrade','uninstall','doctor'],fields:[
    field('package_name','npm 套件名稱',values.package_name.trim()),
    field('scope','安裝範圍',values.scope,['user','project']),
    field('directory','安裝 prefix／專案絕對目錄',values.npm_directory.trim()),
    field('node','Node 絕對路徑',values.node.trim()),field('npm','npm CLI 絕對路徑',values.npm.trim()),
    field('version','遠端套件版本',values.package_version.trim())]};
}
export function copyPluginDocument(manifest) {
  if (!['commands','npm','compose'].includes(manifest.driver)) throw new Error('此插件使用專用備份介面，請匯出 JSON 參考其設定');
  return {...structuredClone(manifest),id:'',label:manifest.label+'（自訂）',version:'1.0.0'};
}
export function parsePluginDocument(text) {
  if (new TextEncoder().encode(text).length > 131072) throw new Error('插件文件上限為 128 KiB');
  const value = JSON.parse(text);
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('請提供 plugin.json 物件');
  return value;
}
export function downloadPlugin(manifest) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(manifest,null,2)+'\n'], {type:'application/json'}));
  const link = document.createElement('a');
  link.href = url; link.download = `${manifest.id}-${manifest.version}.json`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function openPluginEditor(mode, request, onSaved, source = null) {
  const dialog = document.createElement('dialog');
  dialog.className = 'plugin-editor';
  dialog.setAttribute('aria-labelledby','plugin-editor-title');
  document.body.append(dialog);
  let busy = false, preview = null;
  const input = (label,name,value='',required=true) => `<label class="field">${label}<input name="${name}" value="${esc(value)}" ${required?'required':''}></label>`;
  dialog.innerHTML = `<form><div class="modal-head"><h2 id="plugin-editor-title">${mode==='create'?'建立插件':mode==='copy'?'複製並自訂插件':'匯入插件'}</h2><button type="button" class="button compact" data-editor="close">關閉</button></div><div class="modal-body">
    <p>儲存到中央插件目錄後，請再按 Install。命令在所選主機執行；請勿填入密碼或私鑰。</p>
    <div class="plugin-edit-fields">${mode==='create' ? `
      ${input('插件 ID（小寫英文、數字、連字號）','id')}${input('顯示名稱','label')}${input('版本','version','1.0.0')}${input('作者','author','',false)}${input('說明','description','',false)}
      <label class="field">對象類型<select name="kind"><option value="service">常駐服務</option><option value="tool">一次性工具</option><option value="package">套件／CLI</option><option value="extension">擴充插件</option></select></label>
      <label class="field">管理方式<select name="driver"><option value="commands">自訂命令</option><option value="compose">Docker Compose</option><option value="npm">npm</option></select></label>
      <div data-kind="extension" hidden>${input('相容的宿主插件 ID（逗號分隔，可留空）','hosts','',false)}</div>
      <div data-driver="compose" hidden>${input('Compose 專案絕對目錄','compose_dir','/opt/stacks/example')}<p>提供狀態、啟動、停止、重啟及升級。遠端須已有 Compose 專案。</p></div>
      <div data-driver="npm" hidden>${input('npm 套件名稱','package_name')}<label class="field">安裝範圍<select name="scope"><option value="user">使用者 prefix</option><option value="project">專案</option></select></label>${input('安裝 prefix／專案絕對目錄','npm_directory','/opt/npm')}${input('Node 絕對路徑','node','/usr/bin/node')}${input('npm CLI 絕對路徑','npm','/usr/share/nodejs/npm/bin/npm-cli.js')}${input('遠端套件版本（latest 或完整版本號）','package_version','latest')}<p>提供狀態、安裝、升級、卸載及環境檢查。插件版本與遠端套件版本分開管理。</p></div>
      <div data-driver="commands">${input('遠端工作目錄','directory','/opt')}
      <h3>操作命令</h3><p>只填需要的操作。狀態命令輸出 active / stopped 或狀態 JSON。遠端程式及腳本須先準備好。</p>
      ${Object.entries(commandActions).map(([id,label])=>`<label class="field">${label}命令<textarea name="cmd_${id}" rows="2" spellcheck="false"></textarea></label>`).join('')}
      <h3>自訂參數</h3><p>欄位 mode 對應環境變數，命令中使用 "$UNIFIED_MODE"。</p><div id="plugin-parameters"></div><button type="button" class="button" data-editor="parameter">增加參數</button></div>
      ` : `<label class="field">選擇 JSON 文件<input type="file" accept=".json,application/json" id="plugin-file"></label><label class="field">或貼上 plugin.json<textarea name="document" rows="14" required spellcheck="false"></textarea></label>`}
    </div><div class="plugin-preview" hidden></div><p class="form-error" role="alert"></p></div>
    <div class="modal-foot"><button type="button" class="button" data-editor="back" hidden>返回編輯</button><button type="submit" class="button primary">校驗與預覽</button></div></form>`;
  const form = dialog.querySelector('form'), error = dialog.querySelector('[role=alert]');
  if (mode === 'copy') {
    form.elements.document.value = JSON.stringify(copyPluginDocument(source),null,2);
    dialog.querySelector('#plugin-file').closest('label').remove();
    const hint = document.createElement('p'); hint.textContent = '請填寫新的 ID；完整設定已保留，可在 JSON 中修改。原插件保留。';
    dialog.querySelector('.plugin-edit-fields').prepend(hint);
  }
  const syncMethod = () => {
    const kind = form.elements.kind.value;
    for (const option of form.elements.driver.options) option.disabled = option.value === 'compose' ? kind !== 'service' : option.value === 'npm' ? !['package','extension'].includes(kind) : false;
    if (form.elements.driver.selectedOptions[0].disabled) form.elements.driver.value='commands';
    dialog.querySelectorAll('[data-driver], [data-kind]').forEach(panel=>{
      panel.hidden = panel.dataset.driver ? panel.dataset.driver !== form.elements.driver.value : panel.dataset.kind !== kind;
      panel.querySelectorAll('input,select,textarea').forEach(el=>el.disabled=panel.hidden);
    });
  };
  if (mode === 'create') {form.elements.kind.addEventListener('change',syncMethod);form.elements.driver.addEventListener('change',syncMethod);syncMethod();}
  const setBusy = value => {busy=value; dialog.querySelectorAll('button').forEach(b=>b.disabled=value);};
  dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
  dialog.addEventListener('close',()=>dialog.remove());
  dialog.addEventListener('click',e=>{
    const action=e.target.closest('[data-editor]')?.dataset.editor;
    if (!action || busy) return;
    if(action==='close') dialog.close();
    if(action==='back') {preview=null;dialog.querySelector('.plugin-edit-fields').hidden=false;dialog.querySelector('.plugin-preview').hidden=true;form.querySelector('[type=submit]').textContent='校驗與預覽';e.target.hidden=true;error.textContent='';}
    if(action==='parameter') {
      if(dialog.querySelectorAll('.plugin-parameter').length>=22){error.textContent='最多 22 個自訂參數';return;}
      const row=document.createElement('fieldset'); row.className='plugin-parameter';
      row.innerHTML=`<legend>參數</legend>${input('欄位名稱（小寫英文、數字、底線）','param_name')}${input('顯示標籤','param_label')}${input('預設值','param_initial','',false)}${input('選項（以逗號分隔，可留空）','param_choices','',false)}<label><input type="checkbox" name="param_required" checked>必填</label> <button class="button compact" type="button" data-editor="remove">移除參數</button>`;
      dialog.querySelector('#plugin-parameters').append(row);
    }
    if(action==='remove') e.target.closest('fieldset').remove();
  });
  dialog.querySelector('#plugin-file')?.addEventListener('change',async e=>{
    const file=e.target.files[0];if(!file)return;
    error.textContent=''; setBusy(true);
    try{if(file.size>131072)throw new Error('插件文件上限為 128 KiB'); const text=await file.text();parsePluginDocument(text);form.elements.document.value=text;}
    catch(err){error.textContent=err.message;}finally{setBusy(false);}
  });
  form.addEventListener('submit',async e=>{
    e.preventDefault();e.stopPropagation();if(busy)return;
    error.textContent='';setBusy(true);
    try{
      if(preview){
        await request('/plugin-documents',{manifest:preview,create_only:mode==='copy'});
        dialog.close();await onSaved();return;
      }
      const values=Object.fromEntries(new FormData(form));
      const parameters=Array.from(dialog.querySelectorAll('.plugin-parameter')).map(row=>{
        const get=n=>row.querySelector(`[name="param_${n}"]`);
        return {name:get('name').value.trim(),label:get('label').value.trim(),initial:get('initial').value,required:get('required').checked,choices:get('choices').value.split(',').map(v=>v.trim()).filter(Boolean)};
      });
      const manifest=mode==='create'?pluginManifest(values,parameters):parsePluginDocument(values.document);
      if(mode==='copy' && manifest.id===source.id) throw new Error('請使用不同於原插件的新 ID');
      const result=await request('/plugin-documents/validate',{manifest,create_only:mode==='copy'});
      if(mode==='copy' && (result.replaces_version || result.installed_version)) throw new Error('此 ID 已存在，請選擇新的 ID');
      if(!dialog.isConnected)return;
      preview=result.manifest;
      dialog.querySelector('.plugin-edit-fields').hidden=true;
      const panel=dialog.querySelector('.plugin-preview');panel.hidden=false;
      panel.innerHTML=`<h3>${esc(preview.label)} · ${esc(preview.version)}</h3><p>${esc(preview.id)} · ${esc(preview.category)} · ${esc(preview.driver)}</p><p>${result.replaces_version?`取代可安裝版本 ${esc(result.replaces_version)}。`:''}${result.installed_version?`目前已安裝 ${esc(result.installed_version)}；儲存後需手動更新。`:'儲存後尚未安裝。'}</p><p>請確認下方完整參數與命令：</p><pre></pre>`;
      panel.querySelector('pre').textContent=JSON.stringify(preview,null,2);
      form.querySelector('[type=submit]').textContent='儲存到可安裝';dialog.querySelector('[data-editor=back]').hidden=false;
      dialog.querySelector('.modal-body').scrollTop=0;
    }catch(err){error.textContent=err.message;}finally{setBusy(false);}
  });
  dialog.showModal();
}
