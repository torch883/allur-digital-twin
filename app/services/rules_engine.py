from datetime import datetime, time, timedelta
from collections import defaultdict
from sqlalchemy import select
from app.models import Incident, Recommendation, QualityRecord, ProductionRecord, DowntimeEvent, Equipment, Stage
from app.services.kpi_service import calculate_kpi

def ensure_incident(db, *, key, stage_id=None, equipment_id=None, severity='warning', type='throughput', title, description, source='rule', at=None, is_demo=False, action='Проверить состояние участка и первичные данные', effect='Подтвердить причину отклонения и выбрать действие'):
    existing=db.scalar(select(Incident).where(Incident.event_key==key))
    if existing: return existing, False
    incident=Incident(event_key=key,stage_id=stage_id,equipment_id=equipment_id,severity=severity,type=type,title=title,description=description,source=source,created_at=at or datetime.utcnow(),is_demo=is_demo,status='open')
    db.add(incident);db.flush()
    db.add(Recommendation(incident_id=incident.id,stage_id=stage_id,action=action,expected_effect=effect,created_at=incident.created_at))
    return incident, True

def quality_severity(value):
    return 'critical' if value>4 else ('warning' if value>2 else None)

def downtime_severity(minutes,critical):
    if not critical: return None
    return 'critical' if minutes>60 else ('warning' if minutes>=50 else None)

def evaluate_historical(db):
    names={s.id:s.name for s in db.scalars(select(Stage)).all()}
    qualities=db.scalars(select(QualityRecord).where(QualityRecord.is_synthetic==False)).all()
    qmap={(q.date,q.stage_id):q for q in qualities}
    for q in qualities:
        pct=100*q.defects/q.produced if q.produced else 0
        severity=quality_severity(pct)
        if severity:
            ensure_incident(db,key=f'quality:{q.id}',stage_id=q.stage_id,severity=severity,type='quality',title=f'{names[q.stage_id]}: брак {pct:.2f}%',description=f'{q.defects} из {q.produced}; допустимо ≤ 2%. Данные кейса, {q.date}.',at=datetime.combine(q.date,time(16)),action='Проверить категории дефектов, партии и параметры процесса; для окраски — Камеру-02 и фильтры',effect='Снизить повторяемость дефектов после подтверждения причины')
    for p in db.scalars(select(ProductionRecord).where(ProductionRecord.is_synthetic==False)).all():
        if p.fact/p.plan<.95:
            ensure_incident(db,key=f'throughput:{p.id}',stage_id=p.stage_id,title=f'{names[p.stage_id]}: выполнение плана {p.fact/p.plan*100:.1f}%',description=f'{p.fact} / {p.plan}, {p.date}',at=datetime.combine(p.date,time(16)))
        if p.load_pct<90:
            ensure_incident(db,key=f'load:{p.id}',stage_id=p.stage_id,title=f'{names[p.stage_id]}: низкая загрузка',description=f'Загрузка {p.load_pct}% < 90%',at=datetime.combine(p.date,time(16)))
        q=qmap.get((p.date,p.stage_id))
        if q:
            oee=calculate_kpi(p.plan,p.fact,p.run_hours,1,q.produced,q.defects)['oee']
            if oee<85:
                ensure_incident(db,key=f'oee:{p.id}',stage_id=p.stage_id,severity='info',title=f'{names[p.stage_id]}: OEE {oee:.1f}% по демо-методике',description='Цель 85%. Значение зависит от допущения 16 ч/сутки; уточните период исходной строки.',at=datetime.combine(p.date,time(16)),action='Уточнить сменность и плановое время перед производственным решением',effect='Получить сопоставимый показатель OEE')
    equipment={e.id:e for e in db.scalars(select(Equipment)).all()}
    daily=defaultdict(list)
    for d in db.scalars(select(DowntimeEvent).where(DowntimeEvent.is_synthetic==False,DowntimeEvent.is_demo==False,DowntimeEvent.kind=='unplanned')).all():
        daily[(d.equipment_id,d.started_at.date())].append(d)
    for (eid,day),events in daily.items():
        minutes=sum(d.duration_min for d in events);eq=equipment[eid]
        severity=downtime_severity(minutes,eq.critical)
        if severity:
            ensure_incident(db,key=f'downtime:{eid}:{day}',stage_id=eq.stage_id,equipment_id=eid,severity=severity,type='downtime',title=f'{eq.code}: '+('лимит 60 мин почти исчерпан' if minutes<=60 else 'лимит 60 мин превышен'),description=f'{minutes:g} мин за {day}. Критичность оборудования задана для демо.',at=events[0].started_at,action=f'Проверить {eq.code} и подготовить восстановление',effect=f'Сократить риск повторного простоя; наблюдавшийся простой {minutes:g} мин')
    db.flush()
