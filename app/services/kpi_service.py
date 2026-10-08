from datetime import date, datetime, timedelta
from collections import defaultdict
from sqlalchemy import select
from app.models import Stage, ProductionRecord, QualityRecord, DowntimeEvent, MonthlyPlan
from app.config import settings

CASE_START, CASE_END = date(2026,10,1), date(2026,10,2)
METHODOLOGY = 'Демо-методика задания: A = часы / (16 × число дней); P = факт / план; Q = годные / выпущено. Смена исходных строк неизвестна; план принят суточным. Это не валидированный промышленный OEE.'

def calculate_kpi(plan, fact, run_hours, days, produced, defects):
    availability = run_hours/(16*days) if days else 0
    performance = fact/plan if plan else 0
    quality = (produced-defects)/produced if produced else 0
    return dict(plan=plan, fact=fact, good=produced-defects, defects=defects,
        run_hours=round(run_hours,2), availability=round(availability*100,2), performance=round(performance*100,2),
        quality=round(quality*100,2), defect_pct=round((1-quality)*100,3) if produced else 0,
        oee=round(availability*performance*quality*100,2), target_oee=85,
        effective_capacity=round(availability*performance,4))

def kpis(db, start=CASE_START, end=CASE_END, stage_code=None):
    stages=db.scalars(select(Stage).where(Stage.type=='production').order_by(Stage.order)).all()
    result=[]
    for s in stages:
        if stage_code and s.code!=stage_code: continue
        p=db.scalars(select(ProductionRecord).where(ProductionRecord.stage_id==s.id,ProductionRecord.date.between(start,end))).all()
        q=db.scalars(select(QualityRecord).where(QualityRecord.stage_id==s.id,QualityRecord.date.between(start,end))).all()
        d=db.scalars(select(DowntimeEvent).where(DowntimeEvent.stage_id==s.id,DowntimeEvent.started_at>=datetime.combine(start,datetime.min.time()),DowntimeEvent.started_at<datetime.combine(end+timedelta(days=1),datetime.min.time()),DowntimeEvent.is_demo==False)).all()
        k=calculate_kpi(sum(x.plan for x in p),sum(x.fact for x in p),sum(x.run_hours for x in p),len({x.date for x in p}),sum(x.produced for x in q),sum(x.defects for x in q))
        k.update(code=s.code,name=s.name,stage_id=s.id,load_pct=round(sum(x.load_pct for x in p)/len(p),2) if p else 0,
            downtime_min=sum(x.duration_min for x in d),planned_downtime_min=sum(x.duration_min for x in d if x.kind=='planned'),
            has_data=bool(p),is_synthetic=any(x.is_synthetic for x in p), provenance='mixed' if any(x.is_synthetic for x in p) and any(not x.is_synthetic for x in p) else ('synthetic' if any(x.is_synthetic for x in p) else 'case'))
        result.append(k)
    active=[k for k in result if k['has_data']]
    bottleneck=min(active,key=lambda k:k['effective_capacity']) if active else None
    final=next((x for x in result if x['code']=='assembly'),None)
    return dict(stages=result,plant_oee=bottleneck['oee'] if bottleneck else None,bottleneck=bottleneck['code'] if bottleneck else None,
        final_output=final['fact'] if final else None, final_good=final['good'] if final else None,
        downtime_min=sum(x['downtime_min'] for x in result),methodology=METHODOLOGY,from_date=str(start),to_date=str(end),
        plant_oee_note='OEE выбранного расчётного узкого места. Буферы учитываются отдельно в live-модели.')

def monthly_plan(db):
    plans=db.scalars(select(MonthlyPlan).where(MonthlyPlan.month=='2026-10')).all()
    assembly=db.scalar(select(Stage).where(Stage.code=='assembly'))
    actual=sum(db.scalars(select(ProductionRecord.fact).where(ProductionRecord.stage_id==assembly.id,ProductionRecord.date.between(CASE_START,CASE_END),ProductionRecord.is_synthetic==False)).all())
    return dict(month='2026-10',target=5500,models_total=sum(x.quantity for x in plans),actual=actual,actual_as_of='2026-10-02',
        progress_pct=round(actual/5500*100,2),models=[dict(model=x.model,plan=x.quantity,actual=None,progress_pct=None) for x in plans],
        data_warning='Сумма моделей 4 800 против целевых 5 500. Не распределены 700 автомобилей.',
        model_note='В исходных данных нет выпуска по моделям. Прогресс по моделям не определён; общий факт — выпуск сборки, до итогового контроля.')
