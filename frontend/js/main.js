import {$,$$,esc,toast,loading,error,closePanel,names} from './ui.js';
import {api,post,isOffline,setOffline,subscribeConnection,beginOfflineSupport} from './api.js';
import {connectLive} from './ws.js';
import {plantPage,loadPlant,updatePlant,showStage,showEquipment,refreshTimeline,selectSnapshot,showLive,exitHistory,isHistorical,renderInsights} from './plant-map.js';
import {renderDashboard} from './dashboard.js';
import {renderIncidents,actOnIncident} from './incidents.js';
import {renderForecast} from './forecast.js';
import {renderImpact} from './impact.js';
import {renderArchitecture} from './architecture.js';
import {startPresentation,stop as stopPresentation} from './presentation.js';
$$('[data-tab]').forEach(b=>{const label=b.childNodes[1]?.textContent?.trim()||b.textContent.trim();b.setAttribute('aria-label',label);b.title=label;});
let tab='plant',selectedStage=null,lastPlant=null,navVersion=0,ticks=0,wsOnline=false;
function connection(){const el=$('#connection');el.className='connection '+(isOffline()?'offline':wsOnline?'':'connecting');el.innerHTML=`<i></i>${isOffline()?'Офлайн-режим':wsOnline?'Live · подключено':'API · переподключение'}`;}
subscribeConnection(value=>{connection();if(value)toast('Офлайн-режим: встроенный снимок и локальная симуляция');});
export async function navigate(name){const allowed=['plant','dashboard','incidents','forecast','impact','architecture'];if(!allowed.includes(name))name='plant';tab=name;document.documentElement.dataset.view=name;selectedStage=null;closePanel();exitHistory();const version=++navVersion;location.hash=name;$$('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));$('#content').innerHTML=loading();
  try{if(name==='plant'){$('#content').innerHTML=plantPage();lastPlant=await loadPlant();}else if(name==='dashboard')await renderDashboard();else if(name==='incidents')await renderIncidents();else if(name==='forecast')await renderForecast();else if(name==='impact')await renderImpact();else renderArchitecture();if(version===navVersion)$('#content').focus({preventScroll:true});}catch(e){if(version===navVersion)$('#content').innerHTML=error(e);}
}
async function stage(code){selectedStage=code;await showStage(code);}
async function simulation(body){const result=await post('/api/simulation',body);if($('#simulation-toggle'))$('#simulation-toggle').checked=result.enabled;$$('[data-speed]').forEach(b=>b.classList.toggle('active',+b.dataset.speed===result.speed));return result;}
async function scenario(name){exitHistory();await post('/api/scenarios/'+name);if(name!=='reset')await simulation({enabled:true,speed:+($('[data-speed].active')?.dataset.speed||1)});lastPlant=await api('/api/plant');if(tab==='plant'){updatePlant(lastPlant);if($('#snapshot-banner'))$('#snapshot-banner').innerHTML='';await refreshTimeline();const d=await api('/api/dashboard');renderInsights(d.decisions);}toast(name==='reset'?'Демонстрация сброшена. Данные кейса сохранены.':`Сценарий запущен: ${ {conveyor_failure:'поломка конвейера',paint_defect_spike:'всплеск брака',supply_disruption:'сбой поставки'}[name]}`);return lastPlant;}
async function onLive(event){try{if(event.type==='kpi_update'||event.type==='scenario'){
    const state=event.payload;$('#footer-time').textContent=`Виртуальное время ${state.at.replace('T',' ').slice(0,16)} · ${isOffline()?'локальная':'серверная'} симуляция`;$('#incident-badge').textContent=state.incident_count;
    if(lastPlant){lastPlant.state=state;lastPlant.stages.forEach(s=>{if(state.stages[s.code])s.kpi=state.stages[s.code];else s.kpi.inventory=s.kpi.fact=state.inventory[s.code]??state.inventory.finished;s.equipment.forEach(e=>e.status=state.equipment_status[e.code]||(['idle','down'].includes(s.kpi.status)?'idle':'running'));});if(tab==='plant')updatePlant(lastPlant);}
    if(++ticks%5===0&&tab==='plant'){await refreshTimeline();const d=await api('/api/dashboard');renderInsights(d.decisions);}
  }else if(event.type==='incident_created'){const s=lastPlant?.stages.find(s=>s.id===event.payload.stage_id);toast(event.payload.title,s?.code);}}catch(e){console.warn('Live refresh',e);}}
document.addEventListener('click',async e=>{const button=e.target.closest('button,[data-stage],[data-equipment],[data-open-stage]');if(!button)return;try{
  if(button.dataset.incidentAction){e.stopPropagation();button.disabled=true;await actOnIncident(button.dataset.id,button.dataset.incidentAction);return;}
  if(button.dataset.tab){await navigate(button.dataset.tab);return;}
  if(button.dataset.equipment){await showEquipment(button.dataset.equipment);return;}
  if(button.dataset.openStage){const code=button.dataset.openStage;if(tab!=='plant')await navigate('plant');await stage(code);return;}
  if(button.dataset.stage){await stage(button.dataset.stage);return;}
  if(button.hasAttribute('data-close-panel')){closePanel();return;}
  if(button.dataset.scenario){button.disabled=true;await scenario(button.dataset.scenario);button.disabled=false;return;}
  if(button.dataset.speed){await simulation({enabled:$('#simulation-toggle')?.checked??true,speed:+button.dataset.speed});return;}
  if(button.id==='timeline-live'){await showLive();return;}
  if(button.hasAttribute('data-retry')){await navigate(tab);return;}
  if(button.id==='presentation-start')await startPresentation({navigate,stage,simulation,scenario});
}catch(err){button.disabled=false;toast(err.message);}});
document.addEventListener('change',async e=>{try{if(e.target.id==='simulation-toggle'){const speed=+($('[data-speed].active')?.dataset.speed||1);await simulation({enabled:e.target.checked,speed});}if(e.target.id==='timeline-slider')await selectSnapshot(+e.target.value);if(e.target.id==='history-toggle')await showStage(e.target.dataset.historyStage,e.target.checked);}catch(err){toast(err.message);}});
$('#panel-backdrop').onclick=closePanel;document.addEventListener('panelclosed',()=>selectedStage=null);
document.addEventListener('keydown',async e=>{if(e.key==='Escape'){closePanel();stopPresentation();return;}if(e.target.matches('input,select,textarea'))return;if(e.key==='Enter'&&e.target.matches('[data-stage],[data-equipment]')){e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));return;}if(['ArrowLeft','ArrowRight'].includes(e.key)){const codes=Object.keys(names),i=codes.indexOf(selectedStage||'painting'),next=codes[(i+(e.key==='ArrowRight'?1:-1)+codes.length)%codes.length];e.preventDefault();await stage(next);}});
window.addEventListener('hashchange',()=>{const name=location.hash.slice(1);if(name&&name!==tab)navigate(name);});
document.addEventListener('backendrestored',async()=>{connection();toast('Соединение восстановлено. Показано серверное состояние.');await navigate(tab);});
connectLive({onEvent:onLive,onStatus:online=>{wsOnline=online;connection();if(!online)api('/api/health').catch(()=>{});}});
beginOfflineSupport(onLive);
await navigate(location.hash.slice(1)||'plant');connection();
if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(e=>console.warn('Offline cache unavailable',e));
