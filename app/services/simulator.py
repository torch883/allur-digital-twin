import asyncio
import copy
import logging
import math
import random
from datetime import datetime,timedelta
from sqlalchemy import select,delete
from app.models import Stage,Equipment,PlantSnapshot,ScenarioRun,Incident,Recommendation,DowntimeEvent
from app.config import settings
from app.services.rules_engine import ensure_incident,quality_severity,downtime_severity

log=logging.getLogger(__name__)
NAMES={'welding':'Сварка','painting':'Окраска','assembly':'Сборка'}

class Simulator:
    def __init__(self,session_factory,forecast,hub):
        self.sessions=session_factory;self.forecast=forecast;self.hub=hub;self.enabled=settings.simulation_enabled;self.speed=1;self.rng=random.Random(42);self.lock=asyncio.Lock();self.generation=0
        self.state=self.initial_state()

    def initial_state(self):
        stages={}
        for c,f,d in [('welding',60,2.18),('painting',58,4.33),('assembly',60,1.25)]:
            severity=quality_severity(d)
            stages[c]=dict(status=severity or 'running',status_label='Отклонение качества' if severity else 'Работает',fact=float(f),plan=240,load_pct=97,defect_pct=d,run_hours=3.9,downtime_min=0,oee=round(.97*.97*(1-d/100)*100,1),rate_per_hour=15)
        return dict(at='2026-10-03T12:00:00',tick=0,scenario=None,stages=stages,equipment_status={},inventory={'parts':320.,'finished':60.},
            buffers=[dict(id='welded',from_stage='welding',to_stage='painting',qty=8.,capacity=24.,growth_per_min=0),dict(id='painted',from_stage='painting',to_stage='assembly',qty=6.,capacity=20.,growth_per_min=0),dict(id='assembled',from_stage='assembly',to_stage='quality',qty=4.,capacity=16.,growth_per_min=0)],
            is_demo=True,incident_count=0,generation=self.generation)

    def start(self,db):
        prior=db.scalar(select(PlantSnapshot).order_by(PlantSnapshot.id.desc()).limit(1))
        if prior:self.state=copy.deepcopy(prior.state);self.generation=self.state.get('generation',0)
        else:self.persist(db)

    def persist(self,db):
        self.state['incident_count']=len(db.scalars(select(Incident.id).where(Incident.status!='resolved')).all())
        db.add(PlantSnapshot(at=datetime.fromisoformat(self.state['at']),state=copy.deepcopy(self.state)))
        # Bound live history to ~30 minutes real time; case data is retained forever.
        ids=db.scalars(select(PlantSnapshot.id).order_by(PlantSnapshot.id.desc()).offset(720)).all()
        if ids:db.execute(delete(PlantSnapshot).where(PlantSnapshot.id.in_(ids)))
        db.commit()

    def apply_scenario(self,db,name):
        if name=='reset':
            self.generation+=1;self.state=self.initial_state();self.rng=random.Random(42)
            demo_ids=select(Incident.id).where(Incident.is_demo==True)
            db.execute(delete(Recommendation).where(Recommendation.incident_id.in_(demo_ids)))
            db.execute(delete(Incident).where(Incident.is_demo==True))
            db.execute(delete(DowntimeEvent).where(DowntimeEvent.is_demo==True))
            db.execute(delete(PlantSnapshot))
            db.execute(delete(ScenarioRun))
            for eq in db.scalars(select(Equipment)).all():eq.status='running'
        else:
            # One active deterministic scenario; reset first to keep demonstrations repeatable.
            self.apply_scenario(db,'reset')
            self.state['scenario']=name
            self.enabled=True
            at=datetime.fromisoformat(self.state['at']);db.add(ScenarioRun(name=name,started_at=at,active=True))
            code={'conveyor_failure':'assembly','paint_defect_spike':'painting','supply_disruption':'welding'}[name]
            stage=db.scalar(select(Stage).where(Stage.code==code))
            if name=='conveyor_failure':
                self.state['equipment_status']['Конвейер-03']='down';self.state['stages']['assembly'].update(status='down',status_label='Аварийная остановка',load_pct=0,rate_per_hour=0)
                eq=db.scalar(select(Equipment).where(Equipment.code=='Конвейер-03'));eq.status='down'
                db.add(DowntimeEvent(equipment_id=eq.id,stage_id=stage.id,started_at=at,duration_min=0,reason='Сценарий: обрыв цепи',kind='unplanned',resolved=False,is_demo=True))
                title='Конвейер-03: аварийная остановка';description='Сборка остановлена. Буфер после окраски будет заполняться, затем остановится окраска и сварка.';action='Проверить привод и цепь Конвейера-03; организовать восстановление'
            elif name=='paint_defect_spike':
                self.state['stages']['painting']['defect_pct']=8
                self.state['equipment_status']['Камера-02']='warning'
                title='Окраска: всплеск брака до 8%';description='Снижена передача годных изделий на сборку; растёт поток доработки.';action='Проверить Камеру-02, фильтры и режим окраски; подтвердить причину'
            else:
                self.state['inventory']['parts']=0;self.state['stages']['welding'].update(status='idle',status_label='Нет комплектующих',load_pct=0,rate_per_hour=0)
                title='Склад: комплектующие закончились';description='Сварка ожидает поставку. После расходования буферов остановятся окраска и сборка.';action='Согласовать срочную подачу комплектующих и приоритет партий'
            ensure_incident(db,key=f'scenario:{name}:{self.generation}',stage_id=stage.id,equipment_id=eq.id if name=='conveyor_failure' else None,severity='critical',type={'conveyor_failure':'downtime','paint_defect_spike':'quality','supply_disruption':'supply'}[name],title=title,description=description,source='simulator',at=at,is_demo=True,action=action,effect='Восстановить поток; эффект оценивается сценарной моделью')
        self.forecast.refresh(db,self.state);self.persist(db)
        return self.state

    def step(self,db,minutes=None,random_events=True):
        minutes=float(minutes if minutes is not None else self.speed)
        state=self.state;old={b['id']:b['qty'] for b in state['buffers']};at=datetime.fromisoformat(state['at'])+timedelta(minutes=minutes)
        state['at']=at.isoformat();state['tick']+=1
        stages={s.code:s for s in db.scalars(select(Stage)).all()};eqs=db.scalars(select(Equipment)).all()
        # Random failures are rare and automatically repaired after 10–35 virtual minutes.
        timers=state.setdefault('repair_at',{})
        for eq in eqs:
            if eq.code in timers and at>=datetime.fromisoformat(timers[eq.code]):
                state['equipment_status'][eq.code]='running';eq.status='running';del timers[eq.code]
                for d in db.scalars(select(DowntimeEvent).where(DowntimeEvent.equipment_id==eq.id,DowntimeEvent.is_demo==True,DowntimeEvent.resolved==False)).all():d.resolved=True
            if random_events and not state['scenario'] and eq.critical and eq.code not in timers and self.rng.random()<1-math.exp(-minutes/(60*eq.mtbf_hours)):
                state['equipment_status'][eq.code]='down';eq.status='down';timers[eq.code]=(at+timedelta(minutes=self.rng.randint(10,35))).isoformat()
                db.add(DowntimeEvent(equipment_id=eq.id,stage_id=eq.stage_id,started_at=at,duration_min=0,reason='Демо: случайный отказ',kind='unplanned',resolved=False,is_demo=True))
                ensure_incident(db,key=f'random:{self.generation}:{eq.code}:{state["tick"]}',stage_id=eq.stage_id,equipment_id=eq.id,title=f'{eq.code}: остановка',description='Случайный отказ в симуляторе, вероятность по MTBF.',severity='critical',type='downtime',source='simulator',at=at,is_demo=True)
        disabled={next(s.code for s in stages.values() if s.id==e.stage_id) for e in eqs if state['equipment_status'].get(e.code)=='down'}
        b0,b1,b2=state['buffers'];parts=state['inventory']['parts']
        caps={c:15*(1+self.rng.uniform(-.04,.04))*minutes/60 for c in NAMES}
        # Quality spike slows painting to model inspection/rework; explicit demo assumption.
        if state['scenario']=='paint_defect_spike':caps['painting']*=.65
        for c in disabled:
            if c in caps:caps[c]=0
        quality_out=min(b2['qty'],16*minutes/60)
        b2['qty']-=quality_out;state['inventory']['finished']+=quality_out
        # Downstream first, bounded by input inventory and output capacity. No negative buffers.
        assembly=min(caps['assembly'],b1['qty'],b2['capacity']-b2['qty']);b1['qty']-=assembly;b2['qty']+=assembly*(1-state['stages']['assembly']['defect_pct']/100)
        painting=min(caps['painting'],b0['qty'],b1['capacity']-b1['qty']);b0['qty']-=painting;b1['qty']+=painting*(1-state['stages']['painting']['defect_pct']/100)
        welding=min(caps['welding'],parts,b0['capacity']-b0['qty']);state['inventory']['parts']-=welding;b0['qty']+=welding*(1-state['stages']['welding']['defect_pct']/100)
        if state['scenario']!='supply_disruption':state['inventory']['parts']=min(400,state['inventory']['parts']+minutes*.15)
        flow={'welding':welding,'painting':painting,'assembly':assembly}
        for c,s in state['stages'].items():
            qty=flow[c];nominal=15*minutes/60;ratio=qty/nominal if nominal else 0
            s['fact']+=qty;s['load_pct']=round(min(100,ratio*100),1);s['rate_per_hour']=round(qty/minutes*60,2)
            if c in disabled:s.update(status='down',status_label='Аварийная остановка');s['downtime_min']+=minutes
            elif qty<.02:s.update(status='idle',status_label='Буфер заполнен' if (c=='welding' and b0['qty']>=b0['capacity']-.1) or (c=='painting' and b1['qty']>=b1['capacity']-.1) else 'Ожидание подачи');s['downtime_min']+=minutes
            else:
                severity=quality_severity(s['defect_pct']);s.update(status=severity or 'running',status_label='Отклонение качества' if severity else ('Снижена скорость' if ratio<.9 else 'Работает'));s['run_hours']+=minutes/60
            elapsed=max(.1,(at-datetime(2026,10,3,8)).total_seconds()/3600)
            availability=s['run_hours']/elapsed
            s['oee']=round(min(100,availability*min(1,ratio)*(1-s['defect_pct']/100)*100),1)
            if s['status'] in ['idle','down']:
                ensure_incident(db,key=f'cascade:{self.generation}:{c}:{s["status"]}',stage_id=stages[c].id,severity='warning',type='throughput',title=f'{NAMES[c]}: {s["status_label"].lower()}',description='Каскадный эффект в симуляторе. Проверьте соседние буферы и источник остановки.',source='simulator',at=at,is_demo=True,action='Устранить ограничение соседнего участка или восстановить подачу',effect='Возобновить движение изделий по цепочке')
            elif s['load_pct']<90:
                ensure_incident(db,key=f'live-load:{self.generation}:{c}',stage_id=stages[c].id,title=f'{NAMES[c]}: загрузка ниже 90%',description=f'Текущая демо-загрузка {s["load_pct"]}%.',source='simulator',at=at,is_demo=True)
        if random_events and not state['scenario'] and self.rng.random()<.006:
            state['stages']['painting']['defect_pct']=round(self.rng.uniform(4.5,7),2)
            ensure_incident(db,key=f'live-quality:{self.generation}:{state["tick"]}',stage_id=stages['painting'].id,type='quality',severity='critical',source='simulator',title='Окраска: случайный всплеск брака',description='Синтетическое событие качества.',at=at,is_demo=True)
        for b in state['buffers']:b['growth_per_min']=(b['qty']-old[b['id']])/minutes
        for d in db.scalars(select(DowntimeEvent).where(DowntimeEvent.is_demo==True,DowntimeEvent.resolved==False)).all():
            d.duration_min=max(0,(at-d.started_at).total_seconds()/60)
            eq=next(e for e in eqs if e.id==d.equipment_id)
            severity=downtime_severity(d.duration_min,eq.critical)
            if severity:ensure_incident(db,key=f'live-downtime:{self.generation}:{d.id}:{severity}',stage_id=d.stage_id,equipment_id=d.equipment_id,severity=severity,type='downtime',title=f'{eq.code}: '+('лимит 60 мин почти исчерпан' if severity=='warning' else 'простой более 60 мин'),description=f'{d.duration_min:.0f} виртуальных минут в демо.',at=at,source='simulator',is_demo=True)
        if state['tick']%settings.forecast_every_ticks==0:self.forecast.refresh(db,state);self.forecast.anomalies(db,state)
        self.persist(db)
        return state

    async def run(self):
        while True:
            await asyncio.sleep(settings.tick_seconds)
            if not self.enabled:continue
            try:
                async with self.lock:
                    with self.sessions() as db:
                        before=self.state['incident_count'];old_status=copy.deepcopy(self.state['equipment_status']);self.step(db)
                        await self.hub.broadcast('kpi_update',self.state)
                        await self.hub.broadcast('buffer_update',self.state['buffers'])
                        if old_status!=self.state['equipment_status']:await self.hub.broadcast('equipment_status',self.state['equipment_status'])
                        if self.state['incident_count']>before:
                            latest=db.scalar(select(Incident).order_by(Incident.id.desc()).limit(1))
                            await self.hub.broadcast('incident_created',{'id':latest.id,'title':latest.title,'stage_id':latest.stage_id})
                        if self.state['tick']%settings.forecast_every_ticks==0:await self.hub.broadcast('forecast_update',{'revision':self.forecast.cache_revision})
            except asyncio.CancelledError:raise
            except Exception:log.exception('Simulation tick failed')
