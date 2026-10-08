"""Deterministic synthetic history ends before the immutable case dates."""
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from sqlalchemy import select
from app.models import Stage, Equipment, ProductionRecord, QualityRecord, DowntimeEvent, MonthlyPlan, Inventory

STAGES = [('parts','Склад комплектующих','warehouse'),('welding','Сварка','production'),('painting','Окраска','production'),('assembly','Сборка','production'),('quality','Контроль качества','quality'),('finished','Готовая продукция','warehouse')]
EQUIPMENT = {'welding':['ABB-01','ABB-02','ABB-03','ABB-04'], 'painting':['Камера-01','Камера-02','Печь-сушки-01'], 'assembly':['Конвейер-01','Конвейер-02','Конвейер-03','Станция-установки-двигателя'], 'quality':['Стенд-геометрии']}

def seed(db):
    if db.scalar(select(Stage.id).limit(1)) is not None:
        return
    rng = random.Random(42)
    stages = {}
    for i, (code, name, kind) in enumerate(STAGES):
        s = Stage(code=code, name=name, order=i, type=kind)
        db.add(s); db.flush(); stages[code] = s.id
    equipment = {}
    for stage, codes in EQUIPMENT.items():
        for code in codes:
            e = Equipment(stage_id=stages[stage], code=code, name=code,
                critical=code in ['ABB-01','Камера-02','Печь-сушки-01','Конвейер-03','Стенд-геометрии'],
                status='running', last_maintenance_at=datetime(2026,7,1)+timedelta(days=rng.randint(0,25)),
                mtbf_hours=rng.randint(250,650), is_demo=True)
            db.add(e); db.flush(); equipment[code]=e
    source = json.loads(Path(__file__).with_name('seed_data.json').read_text(encoding='utf-8'))
    for d,s,p,f,h,l in source['production']:
        db.add(ProductionRecord(date=date.fromisoformat(d), shift=0, stage_id=stages[s],plan=p,fact=f,run_hours=h,load_pct=l,is_synthetic=False))
    for d,s,p,b,pct in source['quality']:
        db.add(QualityRecord(date=date.fromisoformat(d),stage_id=stages[s],produced=p,defects=b,defect_pct=pct,is_synthetic=False))
    for d,s,e,r,m,k in source['downtime']:
        db.add(DowntimeEvent(started_at=datetime.fromisoformat(d+'T10:00:00'), stage_id=stages[s],equipment_id=equipment[e].id,reason=r,duration_min=m,kind=k,resolved=True,time_assumed=True))
    for model, quantity in source['plans']:
        db.add(MonthlyPlan(month='2026-10',model=model,quantity=quantity))
    # 60 full days, never rewrite the two case dates; one daily aggregate (shift=0).
    for i in range(60):
        d=date(2026,10,1)-timedelta(days=60-i)
        for code in ['welding','painting','assembly']:
            downtime = 0
            for ec in EQUIPMENT[code]:
                eq=equipment[ec]
                age=max(0,(datetime.combine(d,datetime.min.time())-eq.last_maintenance_at).total_seconds()/3600)
                hazard=.018 + .045*min(age/eq.mtbf_hours,3)
                if rng.random()<hazard:
                    minutes=rng.randint(12,90); downtime+=minutes
                    db.add(DowntimeEvent(equipment_id=eq.id,stage_id=stages[code],started_at=datetime.combine(d,datetime.min.time())+timedelta(hours=rng.randint(8,20)),duration_min=minutes,reason=rng.choice(['Сбой привода','Ошибка датчика','Перегрев']),kind='unplanned',resolved=True,is_synthetic=True))
            hours=max(10,15.6-downtime/60-rng.uniform(0,.4))
            rate=15*(1-.0008*i if code=='painting' else 1)
            fact=max(1,round(hours*rate+rng.gauss(0,4)))
            defects=max(0,round(fact*((.017+.00025*i) if code=='painting' else .012)+rng.gauss(0,1)))
            db.add(ProductionRecord(date=d,shift=0,stage_id=stages[code],plan=240,fact=fact,run_hours=round(hours,2),load_pct=round(hours/16*100,1),is_synthetic=True))
            db.add(QualityRecord(date=d,stage_id=stages[code],produced=fact,defects=defects,defect_pct=round(defects/fact*100,2),is_synthetic=True))
    db.add_all([Inventory(code='parts',name='Комплекты для сборки',quantity=320,is_demo=True),Inventory(code='finished',name='Готовые автомобили',quantity=240,is_demo=True)])
    db.commit()
