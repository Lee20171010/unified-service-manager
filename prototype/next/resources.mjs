// Managed-object rules for the UI prototype. All observations and mutations are Mock.
export const resourceKinds = {service:'常駐服務',package:'套件／CLI',extension:'應用插件',tool:'一次性工具'};
export const packagePlugins = ['npm-packages','billion-context','oc-codex-multi-auth'];
export const isPackage = r => ['package','extension'].includes(r.kind);
export const scopeNames = {user:'使用者安裝範圍',project:'專案安裝範圍',managed:'宿主管理的套件範圍'};
const on = (s,p) => s.plugins[p]?.state === 'active';
const ongoing = j => ['queued','running','waiting'].includes(j.status);
const normalizePath = value => {
 const out=[];for(const part of value.split('/')){if(part==='..')out.pop();else if(part&&part!=='.')out.push(part);}return '/'+out.join('/');
};
export function installKey(r){return JSON.stringify([r.host,r.account,r.runtime,r.scope,normalizePath(r.location),r.packageName]);}
export function bindingHosts(s,r){
 const supported=r.plugin==='billion-context'?['opencode','hermes']:r.plugin==='oc-codex-multi-auth'?['opencode']:[];
 return s.services.filter(p=>p.kind!=='package'&&p.kind!=='extension'&&p.kind!=='tool'&&p.host===r.host&&supported.includes(p.plugin)&&s.hosts.find(h=>h.id===p.host)?.user===r.account);
}
export function createPackage(s,data,newId){
 const h=s.hosts.find(h=>h.id===data.host);
 if(!h||!on(s,data.plugin)||!packagePlugins.includes(data.plugin))throw Error('請先選擇可用的管理插件及主機');
 const name=(data.packageName||'').trim();
 if(!/^(?:@[a-z0-9][a-z0-9._-]*\/)?[a-z0-9][a-z0-9._-]*$/.test(name))throw Error('請填 npm 套件名稱；版本與路徑分開設定');
 if(data.plugin!=='npm-packages'&&name!==data.plugin)throw Error('專用接入的套件名稱必須相符');
 if(!['user','project','managed'].includes(data.scope))throw Error('安裝範圍無效');
 if(!data.location?.startsWith('/')||!data.runtime?.startsWith('/'))throw Error('範圍目錄與 Node 路徑請填絕對路徑');
 if(!data.name?.trim())throw Error('請填顯示名稱');
 if(!['fixed','latest'].includes(data.versionPolicy))throw Error('版本策略無效');
 if(data.versionPolicy==='fixed'&&!/^[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?$/.test(data.targetVersion||''))throw Error('固定版本請填明確版本，例如 1.2.3');
 const r={...data,id:newId,kind:data.plugin==='oc-codex-multi-auth'?'extension':'package',name:data.name.trim(),packageName:name,account:h.user,location:normalizePath(data.location),method:data.plugin==='npm-packages'?'npm 套件管理':'專用接入流程',bindings:[],installed:data.initial==='installed',version:data.initial==='installed'?'1.0.0-mock':null,observedAt:Date.now()};
 if(s.services.some(p=>isPackage(p)&&installKey(p)===installKey(r)))throw Error('同一安裝範圍已有此套件，請到現有物件管理宿主接入');
 s.services.push(r);return r;
}
export function addBinding(s,r,parentId){
 if(!bindingHosts(s,r).some(p=>p.id===parentId))throw Error('宿主必須是同主機、同執行帳號且相容的應用');
 if(s.jobs.some(j=>ongoing(j)&&(j.service===r.id||(j.lockKeys||[]).includes(`app:${parentId}`))))throw Error('相關任務尚未結束，暫時不能調整關聯');
 if(r.bindings.some(b=>b.parent===parentId))throw Error('此宿主已經關聯');
 r.bindings.push({parent:parentId,registered:false,loadedVersion:null,needsRestart:false});
}
export function resourceActions(s,r){
 if(!on(s,r.plugin))return [];
 if(!isPackage(r))return r.kind==='tool'?['run']:['refresh','upgrade','start','stop','restart'];
 return ['refresh',...(r.installed?['upgrade','uninstall',...(r.plugin!=='npm-packages'?['doctor']:[])]:['install'])];
}
export function resourceLocks(s,r){
 if(!isPackage(r))return [r.id,`app:${r.id}`];
 return [r.id,`package:${installKey(r)}`,...r.bindings.map(b=>`app:${b.parent}`)];
}
export function checkResourceOperation(s,r,action,bindingId){
 if(!on(s,r.plugin))throw Error('管理插件未安裝或已停用');
 if(['register','unregister'].includes(action)){
  const b=r.bindings?.find(b=>b.parent===bindingId),parent=s.services.find(p=>p.id===bindingId);
  if(!isPackage(r)||!r.installed||!b||!parent||!on(s,parent.plugin))throw Error('套件、宿主或管理插件尚未就緒');
  if((action==='register')===b.registered)throw Error('接入狀態已改變，請重新查看');
 }else if(!resourceActions(s,r).includes(action))throw Error('此物件不支援該操作');
 if(action==='uninstall'&&r.bindings.some(b=>b.registered||b.loadedVersion))throw Error('請先解除所有宿主接入，並重新啟動仍載入此套件的宿主');
}
export function applyResourceResult(s,r,j){
 if(isPackage(r)){
  if(['install','upgrade'].includes(j.action)){
   r.installed=true;r.version=j.resolvedVersion;
   for(const b of r.bindings)if(b.registered)b.needsRestart=b.loadedVersion!==r.version;
  }
  if(j.action==='uninstall'){r.installed=false;r.version=null;}
  if(['register','unregister'].includes(j.action)){
   const b=r.bindings.find(b=>b.parent===j.bindingId);
   b.registered=j.action==='register';b.needsRestart=b.registered?b.loadedVersion!==r.version:!!b.loadedVersion;
  }
  r.observedAt=Date.now();return;
 }
 if(j.action==='stop')r.status='stopped';else if(j.action!=='run')r.status='online';
 if(j.action==='upgrade')r.version='review-new';
 if(['start','restart'].includes(j.action))for(const pkg of s.services.filter(isPackage))for(const b of pkg.bindings){
  if(b.parent===r.id){b.loadedVersion=b.registered&&pkg.installed?pkg.version:null;b.needsRestart=false;}
 }
}
