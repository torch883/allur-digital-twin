import {offlineResponse,offlineTick,offlineState} from './offline-data.js';
let offline=false;const subscribers=new Set();
export const isOffline=()=>offline;
export const subscribeConnection=fn=>{subscribers.add(fn);return()=>subscribers.delete(fn);};
export function setOffline(value){if(offline!==value){offline=value;subscribers.forEach(fn=>fn(value));}}
export async function api(path,options={}){
  if(offline)return offlineResponse(path,options);
  let response;
  try{response=await fetch(path,{method:options.method||'GET',headers:{'Content-Type':'application/json'},body:options.body===undefined?undefined:JSON.stringify(options.body),signal:AbortSignal.timeout(3500),cache:'no-store'});}catch{setOffline(true);return offlineResponse(path,options);}
  const result=await response.json();if(!response.ok)throw Error(result.error?.message||`Ошибка ${response.status}`);return result;
}
export const post=(path,body={})=>api(path,{method:'POST',body});
export function beginOfflineSupport(onTick){
  const tick=setInterval(()=>{if(offline){const s=offlineTick();if(s)onTick({type:'kpi_update',payload:s});}},2500);
  const probe=setInterval(async()=>{if(!offline)return;try{const r=await fetch('/api/health',{signal:AbortSignal.timeout(2000),cache:'no-store'});if(r.ok){setOffline(false);document.dispatchEvent(new Event('backendrestored'));}}catch{}},10000);
  return()=>{clearInterval(tick);clearInterval(probe);};
}
