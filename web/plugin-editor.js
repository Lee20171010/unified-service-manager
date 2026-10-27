const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const commandActions = {refresh:'狀態', start:'啟動', stop:'停止', restart:'重啟', upgrade:'升級', install:'安裝軟體', uninstall:'卸載軟體', doctor:'檢查環境', run:'執行'};
export function commandManifest(values, parameters) {
  const commands = Object.fromEntries(Object.keys(commandActions).filter(a => values['cmd_' + a]?.trim()).map(a => [a, values['cmd_' + a]]));
  if (!Object.keys(commands).length) throw new Error('請至少填寫一項操作命令');
  return {id:values.id.trim(), label:values.label.trim(), version:values.version.trim(), author:values.author.trim(), description:values.description.trim(), interface_version:1, category:'service-management', driver:'commands', resource_kind:values.kind,
    operations:Object.keys(commands), commands,
    fields:[{name:'directory',label:'工作目錄',initial:values.directory.trim(),required:true},{name:'identity',label:'實例名稱',initial:values.id.trim(),required:true}, ...parameters]};
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

export function openPluginEditor(mode, request, onSaved) {
  const dialog = document.createElement('dialog');
  dialog.className = 'plugin-editor';
  dialog.setAttribute('aria-labelledby','plugin-editor-title');
  document.body.append(dialog);
  let busy = false, preview = null;
  const input = (label,name,value='',required=true) => `<label class="field">${label}<input name="${name}" value="${esc(value)}" ${required?'required':''}></label>`;
  dialog.innerHTML = `<form><div class="modal-head"><h2 id="plugin-editor-title">${mode==='create'?'建立命令插件':'匯入插件'}</h2><button type="button" class="button compact" data-editor="close">關閉</button></div><div class="modal-body">
    <p>儲存到中央插件目錄後，請再按 Install。命令在所選主機執行；請勿填入密碼或私鑰。</p>
    <div class="plugin-edit-fields">${mode==='create' ? `
      ${input('插件 ID（小寫英文、數字、連字號）','id')}${input('顯示名稱','label')}${input('版本','version','1.0.0')}${input('作者','author','',false)}${input('說明','description','',false)}
      <label class="field">對象類型<select name="kind"><option value="service">常駐服務</option><option value="tool">一次性工具</option></select></label>${input('遠端工作目錄','directory','/opt')}
      <h3>操作命令</h3><p>只填需要的操作。狀態命令輸出 active / stopped 或狀態 JSON。遠端程式及腳本須先準備好。</p>
      ${Object.entries(commandActions).map(([id,label])=>`<label class="field">${label}命令<textarea name="cmd_${id}" rows="2" spellcheck="false"></textarea></label>`).join('')}
      <h3>自訂參數</h3><p>欄位 mode 對應環境變數，命令中使用 "$UNIFIED_MODE"。</p><div id="plugin-parameters"></div><button type="button" class="button" data-editor="parameter">增加參數</button>
      ` : `<label class="field">選擇 JSON 文件<input type="file" accept=".json,application/json" id="plugin-file"></label><label class="field">或貼上 plugin.json<textarea name="document" rows="14" required spellcheck="false"></textarea></label>`}
    </div><div class="plugin-preview" hidden></div><p class="form-error" role="alert"></p></div>
    <div class="modal-foot"><button type="button" class="button" data-editor="back" hidden>返回編輯</button><button type="submit" class="button primary">校驗與預覽</button></div></form>`;
  const form = dialog.querySelector('form'), error = dialog.querySelector('[role=alert]');
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
        await request('/plugin-documents',{manifest:preview});
        dialog.close();await onSaved();return;
      }
      const values=Object.fromEntries(new FormData(form));
      const parameters=Array.from(dialog.querySelectorAll('.plugin-parameter')).map(row=>{
        const get=n=>row.querySelector(`[name="param_${n}"]`);
        return {name:get('name').value.trim(),label:get('label').value.trim(),initial:get('initial').value,required:get('required').checked,choices:get('choices').value.split(',').map(v=>v.trim()).filter(Boolean)};
      });
      const manifest=mode==='create'?commandManifest(values,parameters):parsePluginDocument(values.document);
      const result=await request('/plugin-documents/validate',{manifest});
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
