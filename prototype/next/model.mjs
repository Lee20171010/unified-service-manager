import {isPackage,resourceLocks,checkResourceOperation,applyResourceResult} from './resources.mjs';
// UI review fixtures only. No commands, SSH connections or storage requests execute.
export const catalog = [
  ['opencode','OpenCode','service-management','應用管理','版本、啟停與互動升級'],
  ['openchamber','OpenChamber','service-management','應用管理','遠端服務狀態與生命週期'],
  ['hermes','Hermes','service-management','應用管理','應用狀態與互動升級'],
  ['chatgpt','ChatGPT','service-management','應用管理','受管軟體來源與啟動方式需配置'],
  ['ssh-service','通用服務／工具','service-management','命令與參數','接入 halogen service、android-test-env、xpu-mode、zentune 或新工具'],
  ['docker-compose','Docker Compose','service-management','Compose 專案','以專案目錄管理服務'],
  ['npm-packages','npm 套件管理','package-management','套件與 CLI','依主機、帳號與安裝範圍管理一般 npm 包'],
  ['billion-context','bili / billion-context','package-management','套件與宿主接入','套件更新、OpenCode / Hermes 接入與載入版本'],
  ['oc-codex-multi-auth','oc-codex-multi-auth','package-management','OpenCode 應用插件','專用安裝更新、接入狀態與診斷'],
  ['magpie','Magpie','application-backup','設定備份','設定快照與還原'],
  ['serverbox','Flutter ServerBox','application-backup','設定備份','設定快照與還原'],
  ['webdav','WebDAV','backup-storage','備份空間','儲存設定快照；搭配應用備份插件'],
].map(([id,name,category,type,description])=>({id,name,category,type,description,version:'0.1.0-preview'}));
export const categories={'service-management':'服務與工具','package-management':'套件與應用插件','application-backup':'應用備份','backup-storage':'備份儲存'};
export const labels={refresh:'更新狀態',upgrade:'升級',start:'啟動',stop:'停止',restart:'重啟',run:'執行',install:'安裝套件',uninstall:'卸載套件',register:'接入宿主',unregister:'解除接入',doctor:'診斷',backup:'備份',restore:'還原'};
export const statuses={queued:'排隊中',running:'執行中',waiting:'等待輸入',success:'成功',failed:'失敗',interrupted:'已中斷'};
export const active=j=>['queued','running','waiting'].includes(j.status);
export function fresh(){return {schema:1,plugins:{},hosts:[],services:[],jobs:[],backups:[],storage:null};}
export function id(prefix){return `${prefix}-${globalThis.crypto.randomUUID().slice(0,8)}`;}
export function available(s,p){return s.plugins[p]?.state==='active';}
export function pluginRefs(s,p){return s.services.filter(x=>x.plugin===p).length+s.backups.filter(b=>b.plugin===p||p==='webdav').length+(p==='webdav'&&s.storage?1:0);}
export function changePlugin(s,p,op){
  if(!catalog.some(x=>x.id===p))throw Error('找不到插件');
  if(op==='install'){s.plugins[p]={state:'active',version:catalog.find(x=>x.id===p).version};return;}
  if(!s.plugins[p])throw Error('尚未安裝插件');
  if(op==='enable'){s.plugins[p].state='active';return;}
  if(s.jobs.some(j=>active(j)&&j.plugins.includes(p)))throw Error('相關任務尚未結束，請先查看任務');
  if(op==='disable'){s.plugins[p].state='disabled';return;}
  if(op==='remove')delete s.plugins[p];
}
export function newJob(s,{target,service=null,action,scenario='interactive',plugin,parameter='',backup=null,bindingId=null}){
  const plugins=['backup','restore'].includes(action)?[plugin,'webdav']:[plugin];
  if(plugins.some(p=>!available(s,p)))throw Error('請先安裝並啟用所需插件');
  if(['backup','restore'].includes(action)&&!s.storage)throw Error('請先設定 WebDAV 備份空間');
  const resource=s.services.find(x=>x.id===service);
  if(resource)checkResourceOperation(s,resource,action,bindingId);
  if(resource&&['register','unregister'].includes(action))plugins.push(s.services.find(p=>p.id===bindingId).plugin);
  const targetKey=service||`backup:${plugin}`;
  const lockKeys=resource?resourceLocks(s,resource):[targetKey];
  if(s.jobs.some(j=>active(j)&&(j.lockKeys||[j.targetKey]).some(k=>lockKeys.includes(k))))throw Error('套件或宿主有相關任務，請先查看執行輸出');
  if(s.jobs.some(j=>active(j)&&j.targetKey===targetKey))throw Error('同一目標已有任務，請先查看執行輸出');
  const j={id:id('job'),target,service,action,scenario,plugin,plugins,targetKey,lockKeys,parameter,backup,bindingId,resolvedVersion:resource&&isPackage(resource)?(resource.versionPolicy==='fixed'?resource.targetVersion:'2.0.0-mock'):null,status:s.jobs.some(active)?'queued':'running',step:0,progress:0,logs:[],date:Date.now(),generation:id('process'),mode:scenario==='pty'?'pty':'stdin'};
  if(action==='upgrade'){
    j.mode='pty';
    const resource=s.services.find(x=>x.id===service),host=s.hosts.find(x=>x.id===resource?.host);
    sessions.set(j,{phase:'foreground',generation:j.generation,cwd:resource?.location?.startsWith('/')?resource.location:'/srv/review',user:host?.user||'admin',hostname:host?.name||'review-host',logs:[]});
  }
  s.jobs.unshift(j); log(j,'system',`已建立 ${labels[action]} 任務 · ${target} · Mock 執行器`);
  if(resource&&isPackage(resource)){log(j,'system',`執行範圍：${resource.account} · ${resource.scope} · ${resource.location} · ${resource.packageName}`);if(['install','upgrade'].includes(action))log(j,'system',`本次固定套件版本：${j.resolvedVersion}（Mock）`);}
  if(action==='upgrade')log(j,'terminal','$ upgrade [configured action · Mock]');
  return j;
}
const sessions = new WeakMap();
export const sessionFor = j => sessions.get(j) || null;
export function log(j,stream,text){j.logs.push({seq:j.logs.length+1,stream,text,time:Date.now()});}
function finish(s,j){
  j.status='success';j.progress=100;log(j,'stdout','操作完成 · exit code 0');
  const service=s.services.find(x=>x.id===j.service);
  if(service)applyResourceResult(s,service,j);
  returnToShell(j);
  if(j.action==='backup')s.backups.unshift({id:id('backup'),plugin:j.plugin,name:catalog.find(p=>p.id===j.plugin).name,date:Date.now(),status:'verified',filename:`${j.plugin}-${Date.now()}.zip`});
}
export function tick(s,j){
  if(j.status==='queued'){
    const first=s.jobs.filter(x=>x.status==='queued').at(-1);
    if(first!==j||s.jobs.some(x=>['running','waiting'].includes(x.status)))return;
    j.status='running';log(j,'system','排隊結束，執行器已開始此任務。');
  }
  if(j.status!=='running')return;
  const resource=s.services.find(r=>r.id===j.service);
  try{if(j.step===0&&resource)checkResourceOperation(s,resource,j.action,j.bindingId);}catch(error){j.status='failed';log(j,'stderr',error.message);returnToShell(j);return;}
  j.step++;j.progress=Math.min(90,j.step*14);
  if(j.step===1)log(j,'stdout','檢查目標設定與執行環境…');
  if(j.step===2){
    if(['backup','restore'].includes(j.action))log(j,'stdout',j.action==='backup'?'建立設定快照並計算 SHA-256…':'驗證 manifest、checksum、路徑與還原目標…');
    else log(j,'stdout',`${labels[j.action]}：準備執行…${j.parameter?' · 已套用本次參數':''}`);
    if(j.action==='upgrade'&&['interactive','pty'].includes(j.scenario)){j.status='waiting';log(j,j.mode==='pty'?'terminal':'stdout','繼續升級？輸入 y 繼續，n 結束。 [y/n]');}
  }
  if(j.step===3){
    if(j.scenario==='fail'){j.status='failed';log(j,'stderr',j.action==='restore'?'模擬錯誤：備份校驗不符，還原已停止，未修改原設定。':j.action==='backup'?'模擬錯誤：WebDAV 上傳失敗，未產生可還原快照。':'模擬錯誤：操作來源無法連線。尚未套用變更；檢查來源與網路後再手動重試。');returnToShell(j);return;}
    log(j,'stdout',j.action==='restore'?'保留目前設定快照，再套用還原內容…':'處理資料… 60%');
  }
  if(j.step===4){log(j,'stdout','驗證操作結果…');if(resource&&isPackage(resource))log(j,'stdout',['upgrade','install','register','unregister'].includes(j.action)?'套件操作完成後，宿主載入版本要在明確重啟後確認；不自動重啟。':'套件安裝範圍檢查完成（Mock）');}
  if(j.step>=5)finish(s,j);
}
function shellLog(session,text){session.logs.push({stream:'shell',text,time:Date.now()});}
export function shellPrompt(session){return `${session.user}@${session.hostname}:${session.cwd}$`;}
function returnToShell(j){
  const session=sessionFor(j);
  if(!session||session.phase==='closed')return;
  session.phase='shell';
  shellLog(session,'── 升級任務結果已保存 · 以下為獨立的手動排錯輸出，不寫入任務日誌 ──');
  shellLog(session,shellPrompt(session));
}
function resolvePath(cwd,path){
  const parts=(path.startsWith('/')?path:cwd+'/'+path).split('/'),out=[];
  for(const p of parts){if(p==='..')out.pop();else if(p&&p!=='.')out.push(p);}
  return '/'+out.join('/');
}
function shellCommand(j,session,text){
  const cmd=text.trim();
  // Prototype simulates a few commands. It never evaluates code or starts processes.
  if(cmd==='clear'){session.logs=[];session.hideJobOutput=true;return;}
  if(session.logs.at(-1)?.text===shellPrompt(session))session.logs.pop();
  shellLog(session,`${shellPrompt(session)} ${text}`);
  if(cmd==='exit'||cmd==='logout'){session.phase='closed';shellLog(session,'logout · Mock shell 已結束');return;}
  let output='';
  if(cmd==='help')output='Mock 指令：pwd、ls、cd <目錄>、whoami、hostname、echo <文字>、ps、status、journalctl、clear、exit。正式版由目標 shell 執行輸入。';
  else if(cmd==='pwd')output=session.cwd;
  else if(cmd==='whoami')output=session.user;
  else if(cmd==='hostname')output=session.hostname;
  else if(cmd==='ls'||cmd.startsWith('ls '))output='config/  logs/  README.md  (Mock)';
  else if(cmd==='cd'||cmd.startsWith('cd ')){session.cwd=resolvePath(session.cwd,cmd.slice(3).trim()||'/home/'+session.user);output='';}
  else if(cmd==='echo'||cmd.startsWith('echo '))output=cmd.slice(5);
  else if(cmd==='ps'||cmd.startsWith('ps '))output='PID  CMD\n101  sh\nMock: 升級前台程序已退出';
  else if(cmd==='status'||cmd.startsWith('systemctl status'))output=`Mock 服務狀態：${j.status==='success'?'online':'unknown · 請重新確認'}\n升級結果：${statuses[j.status]}`;
  else if(cmd.startsWith('journalctl'))output='[Mock] service: review log ready; no real host accessed.';
  else if(cmd)output='Mock 未執行此指令。此處可自由輸入，正式版會交給目標 shell；help 可查看可模擬指令。';
  // Shell echo and output stay in this in-memory session, never in durable job logs.
  if(output)shellLog(session,output);
  shellLog(session,shellPrompt(session));
}
export function sendInput(s,jobId,text,generation){
  const j=s.jobs.find(x=>x.id===jobId),session=j&&sessionFor(j);
  if(!j||!session||session.phase==='closed'||session.generation!==generation)throw Error('工作階段已結束或連線已失效，輸入未送出');
  if(text.length>1024)throw Error('輸入過長');
  if(session.phase==='shell'){shellCommand(j,session,text);return;}
  if(!['running','waiting'].includes(j.status))throw Error('程序尚未啟動或已結束');
  log(j,'system','輸入已送到前台升級程序（不保存原文）');
  if(j.status==='waiting'){
    if(text.trim().toLowerCase()==='y'){j.status='running';log(j,'stdout','程序已確認，繼續升級…');}
    else if(text.trim().toLowerCase()==='n'){j.status='interrupted';log(j,'stdout','程序取消升級，未套用更新。');returnToShell(j);}
    else log(j,'stderr','升級程序：請回答 y 或 n。其他指令需等升級退出或 Ctrl+C 返回 shell 後執行。');
  }else log(j,'terminal','Mock 前台程序收到輸入；這段輸入沒有交給 shell 執行。');
}
export function interrupt(j){
  const session=sessionFor(j);
  if(session?.phase==='shell'){shellLog(session,'^C');shellLog(session,shellPrompt(session));return;}
  if(!['running','waiting'].includes(j.status))throw Error('程序尚未執行或已結束');
  j.status='interrupted';log(j,'system','已模擬 Ctrl+C；前台程序已退出。實際目標狀態需重新查詢。');returnToShell(j);
}
export function closeSession(j){
  const session=sessionFor(j);
  if(!session||session.phase==='closed')return;
  if(active(j))throw Error('升級仍在執行；請先 Ctrl+C 中斷，或收起 Console 保持執行');
  session.phase='closed';shellLog(session,'工作階段已結束');
}
export function recover(s){
  for(const j of s.jobs){
    if(active(j)){j.status='interrupted';log(j,'system','Prototype 頁面已重新載入，模擬執行器中斷；不會自動重跑。');}
    sessions.delete(j);
  }
  return s;
}
