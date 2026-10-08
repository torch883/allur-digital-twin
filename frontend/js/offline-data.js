import {INITIAL} from './offline-snapshot.js';
const clone=x=>structuredClone(x);
let data=clone(INITIAL),state=clone(data['/api/plant'].state),enabled=true,speed=1,history=[],nextId=90000;
const live=()=>{const plant=clone(data['/api/plant']);plant.state=clone(state);plant.stages.forEach(s=>{if(state.stages[s.code])s.kpi=clone(state.stages[s.code]);else s.kpi.inventory=s.kpi.fact=state.inventory[s.code]??state.inventory.finished;s.equipment.forEach(e=>e.status=state.equipment_status[e.code]||(['idle','down'].includes(s.kpi.status)?'idle':'running'));});return plant;};
function addIncident(stage,title,type='throughput',severity='critical'){
  if(data['/api/incidents'].items.some(x=>x.title===title&&x.is_demo))return;
  const s=data['/api/plant'].stages.find(s=>s.code===stage),id=nextId++;
  data['/api/incidents'].items.unshift({id,stage,stage_id:s?.id,stage_name:s?.name,severity,type,title,description:'Локальная офлайн-симуляция. Исходные записи кейса сохранены.',created_at:state.at,status:'open',source:'simulator',is_demo:true,recommendation:{action:'Проверить источник остановки и восстановить поток',expected_effect:'Снизить потери выпуска'}});
}
function bottlenecks(){const stages=Object.entries(state.stages).map(([stage,s])=>{const b=state.buffers.find(b=>b.from_stage===stage),g=b?.growth_per_min||0;return {stage,effective_capacity:s.rate_per_hour*(1-s.defect_pct/100),load_pct:s.load_pct,status:s.status,buffer:b,minutes_to_block:g>.001?Math.max(0,(b.capacity-b.qty)/g):null,minutes_to_empty:g<-.001?b.qty/-g:null};});return {stages,bottleneck:[...stages].sort((a,b)=>(a.effective_capacity-b.effective_capacity)||(Number(a.status!=='down')-Number(b.status!=='down')))[0]?.stage,is_demo:true,assumption:'Локальный симулятор, демонстрационные ёмкости и скорости.'};}
function planForecast(){const p=clone(data['/api/forecast/plan']),m={conveyor_failure:.75,paint_defect_spike:.94,supply_disruption:.7}[state.scenario]||1;['p10','p50','p90'].forEach(k=>p[k]=Math.round(240+(p[k]-240)*m));p.risk_pct=p.p90<p.target?100:p.risk_pct;p.assumptions.push('Офлайн: сохранённый прогноз модели с заданным сценарным коэффициентом; модель не переобучается в браузере.');return p;}
export function offlineTick(){
  if(!enabled)return;
  const min=speed,old=state.buffers.map(b=>b.qty);state.at=new Date(new Date(state.at+'Z').getTime()+min*60000).toISOString().slice(0,19);state.tick++;
  const [b0,b1,b2]=state.buffers,capacity=.25*min,quality=Math.min(b2.qty,min*16/60);b2.qty-=quality;state.inventory.finished+=quality;
  const a=Math.min(state.scenario==='conveyor_failure'?0:capacity,b1.qty,b2.capacity-b2.qty);b1.qty-=a;b2.qty+=a*.9875;
  const p=Math.min(capacity*(state.scenario==='paint_defect_spike'?.65:1),b0.qty,b1.capacity-b1.qty);b0.qty-=p;b1.qty+=p*(1-state.stages.painting.defect_pct/100);
  const w=Math.min(capacity,state.inventory.parts,b0.capacity-b0.qty);state.inventory.parts-=w;b0.qty+=w*.9782;
  if(state.scenario!=='supply_disruption')state.inventory.parts=Math.min(400,state.inventory.parts+.15*min);
  Object.entries({welding:w,painting:p,assembly:a}).forEach(([c,qty])=>{const s=state.stages[c];s.fact+=qty;s.rate_per_hour=qty/min*60;s.load_pct=Math.min(100,qty/capacity*100);
    if(qty<.02){s.status=c==='assembly'&&state.scenario==='conveyor_failure'?'down':'idle';s.status_label=s.status==='down'?'Аварийная остановка':'Ожидание / буфер';s.downtime_min+=min;addIncident(c,`${data['/api/plant'].stages.find(x=>x.code===c).name}: каскадная остановка`,'throughput','warning');}else{s.status=s.defect_pct>4?'critical':s.defect_pct>2?'warning':'running';s.status_label=s.defect_pct>2?'Отклонение качества':'Работает';s.run_hours+=min/60;}s.oee=Math.max(0,Math.min(100,s.load_pct*(1-s.defect_pct/100)));});
  state.buffers.forEach((b,i)=>b.growth_per_min=(b.qty-old[i])/min);state.incident_count=data['/api/incidents'].items.filter(i=>i.status!=='resolved').length;
  history.push({at:state.at,plant:live()});if(history.length>720)history.shift();return clone(state);
}
export function offlineReset(){data=clone(INITIAL);state=clone(data['/api/plant'].state);state.scenario=null;history=[];}
export function offlineState(){return clone(state);}
export function offlineResponse(path,{method='GET',body}={}){
  const url=new URL(path,'http://offline.local'),route=decodeURIComponent(url.pathname),q=url.searchParams;
  if(route==='/api/health')return {status:'offline',mode:'demo'};
  if(route==='/api/plant')return live();
  if(route==='/api/simulation'){if(method==='POST'){enabled=body.enabled;speed=body.speed;}return {enabled,speed,virtual_time:state.at,scenario:state.scenario};}
  if(route.startsWith('/api/scenarios/')){const name=route.split('/').pop();offlineReset();if(name!=='reset'){state.scenario=name;
      if(name==='conveyor_failure'){state.equipment_status['Конвейер-03']='down';Object.assign(state.stages.assembly,{status:'down',status_label:'Аварийная остановка',rate_per_hour:0,load_pct:0});addIncident('assembly','Конвейер-03: аварийная остановка','downtime');}
      if(name==='paint_defect_spike'){state.stages.painting.defect_pct=8;state.equipment_status['Камера-02']='warning';addIncident('painting','Окраска: всплеск брака до 8%','quality');}
      if(name==='supply_disruption'){state.inventory.parts=0;Object.assign(state.stages.welding,{status:'idle',status_label:'Нет комплектующих',rate_per_hour:0,load_pct:0});addIncident('welding','Склад: комплектующие закончились','supply');}}
    return {ok:true,name,state:clone(state)};}
  if(route==='/api/incidents'){let items=clone(data[route].items);['stage','severity','status'].forEach(k=>{if(q.get(k))items=items.filter(i=>i[k]===q.get(k));});if(q.get('from'))items=items.filter(i=>i.created_at.slice(0,10)>=q.get('from'));if(q.get('to'))items=items.filter(i=>i.created_at.slice(0,10)<=q.get('to'));return {items};}
  if(/^\/api\/incidents\/\d+\/(ack|resolve)$/.test(route)){const parts=route.split('/'),i=data['/api/incidents'].items.find(i=>i.id===+parts[3]);if(!i)throw Error('Инцидент не найден');i.status=parts[4]==='ack'?'ack':'resolved';return clone(i);}
  if(route==='/api/dashboard'){const d=clone(data[route]);d.live=clone(state);d.active_incidents=data['/api/incidents'].items.filter(i=>i.status!=='resolved').length;d.decisions=clone(data['/api/incidents'].items.filter(i=>i.status!=='resolved').slice(0,6));d.bottleneck=bottlenecks();return d;}
  if(route==='/api/forecast/bottleneck')return bottlenecks();
  if(route==='/api/forecast/plan')return planForecast();
  if(route==='/api/forecast/refresh')return {risks:data['/api/forecast/downtime'].items,plan:planForecast(),disclaimer:'Офлайн: сохранённые результаты модели; новые параметры сценария пересчитаны локально.'};
  if(route==='/api/forecast/downtime'){const f=clone(data[route]);f.disclaimer+=' Офлайн: сохранённый результат модели, без переобучения.';f.items.forEach(i=>i.currently_down=state.equipment_status[i.equipment]==='down');return f;}
  if(route==='/api/recommendations')return {items:data['/api/incidents'].items.filter(i=>i.status!=='resolved'&&i.recommendation).map(i=>i.recommendation)};
  if(route==='/api/timeline'){if(!history.length)history.push({at:state.at,plant:live()});const at=q.get('at'),snap=at?[...history].reverse().find(x=>x.at<=at):history.at(-1);if(!snap)throw Error('До этого времени снимков нет');return {...clone(snap),available:history.map(x=>x.at),is_demo:true};}
  if(route==='/api/impact'){const p={downtime_reduction_pct:20,defect_reduction_pct:25,downtime_cost_per_hour:150000,defect_cost_per_car:80000,implementation_cost:15000000,operating_days_per_year:250,...body};const h=p.operating_days_per_year,d=9*p.operating_days_per_year,a=h*p.downtime_reduction_pct/100*p.downtime_cost_per_hour,b=d*p.defect_reduction_pct/100*p.defect_cost_per_car;return {annual_savings:a+b,downtime_savings:a,quality_savings:b,payback_months:a+b>0?p.implementation_cost/(a+b)*12:null,inputs:p,currency:'KZT',assumptions:['Офлайн-расчёт на исходных данных: 120 мин неплановых простоев и 18 дефектов на переделах за 2 дня.','Цены, улучшения и 250 рабочих дней — изменяемые допущения.','Простой оборудования не равен простою завода; дефекты переделов не равны уникальным автомобилям.','Затраты на брак считаются на одно исправление. Экономия двух категорий предполагается независимой.','Линейная экстраполяция, простая окупаемость без эксплуатационных расходов и налогов.'],curve:Array.from({length:11},(_,i)=>({reduction_pct:i*10,annual_savings:h*i/10*p.downtime_cost_per_hour+b}))};}
  if(route.startsWith('/api/stages/')){const d=clone(data[route]);if(!d)throw Error('Участок не найден');const code=route.split('/').pop();d.live=clone(state.stages[code]);d.incidents=data['/api/incidents'].items.filter(i=>i.stage===code);return d;}
  if(route.startsWith('/api/equipment/')){const d=clone(data[route]);if(!d)throw Error('Оборудование не найдено');d.status=state.equipment_status[d.code]||'running';return d;}
  if(route==='/api/quality'&&q.get('stage'))return {...clone(data[route]),items:data[route].items.filter(i=>i.stage===q.get('stage'))};
  if(data[route])return clone(data[route]);throw Error('Данные недоступны в офлайн-снимке');
}
