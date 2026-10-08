import copy
from datetime import datetime
from sqlalchemy import select
from fastapi import HTTPException
from app.models import Stage,Equipment,Incident,DowntimeEvent,ProductionRecord,QualityRecord,Recommendation
from app.services.kpi_service import kpis

def row_dict(row):
    return {c.name:(getattr(row,c.name).isoformat() if isinstance(getattr(row,c.name),(__import__('datetime').date,datetime)) else getattr(row,c.name)) for c in row.__table__.columns}

def stage_or_404(db,code):
    stage=db.scalar(select(Stage).where(Stage.code==code))
    if not stage:raise HTTPException(404,'Участок не найден')
    return stage

def incident_dict(db,i):
    d=row_dict(i);s=db.get(Stage,i.stage_id) if i.stage_id else None
    d.update(stage=s.code if s else None,stage_name=s.name if s else 'Завод')
    rec=db.scalar(select(Recommendation).where(Recommendation.incident_id==i.id))
    d['recommendation']=row_dict(rec) if rec else None
    return d

def plant_view(db,state):
    stages=db.scalars(select(Stage).order_by(Stage.order)).all();equipment=db.scalars(select(Equipment)).all();items=[]
    for s in stages:
        k=copy.deepcopy(state['stages'].get(s.code,{}))
        if s.type!='production':
            value=state['inventory'].get(s.code,state['inventory']['finished'])
            k=dict(status='idle' if s.code=='parts' and value==0 else 'running',status_label='Нет комплектующих' if s.code=='parts' and value==0 else 'Работает',fact=round(value),plan=None,load_pct=None,inventory=round(value,1),is_demo=True)
        inherited='idle' if k.get('status') in ['idle','down'] else 'running'
        items.append(dict(id=s.id,code=s.code,name=s.name,order=s.order,type=s.type,kpi=k,equipment=[dict(**{k:v for k,v in row_dict(e).items() if k!='status'},status=state['equipment_status'].get(e.code,inherited)) for e in equipment if e.stage_id==s.id]))
    return dict(stages=items,links=[{'from':stages[i].code,'to':stages[i+1].code} for i in range(len(stages)-1)],state=copy.deepcopy(state),is_demo=True,
        data_note='LIVE — отдельная демонстрационная смена 03.10.2026. Исходные записи 01–02.10 сохранены в детализации.',oee_note='LIVE OEE — оперативная модель по прошедшему времени; исторический OEE использует 16 ч/сутки по заданию.')

def bottleneck_view(state):
    stages=state['stages'];rows=[]
    for code,s in stages.items():
        buffer=next((b for b in state['buffers'] if b['from_stage']==code),None)
        growth=buffer['growth_per_min'] if buffer else 0
        blockage=(buffer['capacity']-buffer['qty'])/growth if buffer and growth>.001 else None
        starvation=buffer['qty']/-growth if buffer and growth<-.001 else None
        rows.append(dict(stage=code,effective_capacity=s['rate_per_hour']*(1-s['defect_pct']/100),load_pct=s['load_pct'],buffer=buffer,minutes_to_block=round(max(0,blockage),1) if blockage is not None else None,minutes_to_empty=round(max(0,starvation),1) if starvation is not None else None,status=s['status']))
    limiting=min(rows,key=lambda r:(r['effective_capacity'],0 if r['status']=='down' else 1)) if rows else None
    return dict(bottleneck=limiting['stage'] if limiting else None,stages=rows,is_demo=True,assumption='Пропускная способность текущего потока годных изделий; время до заполнения по текущему приросту буфера. Ёмкости буферов и скорости заданы для демо.')
