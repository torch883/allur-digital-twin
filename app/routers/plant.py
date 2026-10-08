from fastapi import APIRouter,Depends,Request,HTTPException,Query
from sqlalchemy import select
from datetime import datetime
from app.db import get_db
from app.models import Equipment,Stage,ProductionRecord,QualityRecord,DowntimeEvent,Incident,PlantSnapshot
from app.services.views import plant_view,row_dict,stage_or_404,incident_dict
from app.services.kpi_service import kpis

router=APIRouter(prefix='/api',tags=['Завод'])

@router.get('/plant')
def plant(request:Request,db=Depends(get_db)):
    return plant_view(db,request.app.state.simulator.state)

@router.get('/stages/{code}')
def stage(code:str,request:Request,db=Depends(get_db)):
    s=stage_or_404(db,code)
    return dict(stage=row_dict(s),live=request.app.state.simulator.state['stages'].get(code),
        kpi=kpis(db,stage_code=code),production=[row_dict(x) for x in db.scalars(select(ProductionRecord).where(ProductionRecord.stage_id==s.id).order_by(ProductionRecord.date)).all()],
        quality=[row_dict(x) for x in db.scalars(select(QualityRecord).where(QualityRecord.stage_id==s.id).order_by(QualityRecord.date)).all()],
        downtime=[row_dict(x) for x in db.scalars(select(DowntimeEvent).where(DowntimeEvent.stage_id==s.id).order_by(DowntimeEvent.started_at.desc())).all()],
        incidents=[incident_dict(db,x) for x in db.scalars(select(Incident).where(Incident.stage_id==s.id).order_by(Incident.created_at.desc())).all()],
        forecast=[x for x in request.app.state.forecast.cached['risks'] if x['stage']==code],is_demo=s.type!='production')

@router.get('/equipment/{code}')
def equipment(code:str,request:Request,db=Depends(get_db)):
    e=db.scalar(select(Equipment).where(Equipment.code==code))
    if not e:raise HTTPException(404,'Оборудование не найдено')
    at=datetime.fromisoformat(request.app.state.simulator.state['at']);result=row_dict(e)
    state=request.app.state.simulator.state
    stage_code=db.get(Stage,e.stage_id).code
    inherited='idle' if state['stages'].get(stage_code,{}).get('status') in ['down','idle'] else 'running'
    result.update(status=state['equipment_status'].get(e.code,inherited),hours_since_maintenance=round((at-e.last_maintenance_at).total_seconds()/3600),downtime=[row_dict(x) for x in db.scalars(select(DowntimeEvent).where(DowntimeEvent.equipment_id==e.id).order_by(DowntimeEvent.started_at.desc())).all()],risk=next((x for x in request.app.state.forecast.cached['risks'] if x['equipment']==code),None))
    return result

@router.get('/timeline')
def timeline(request:Request,at:datetime|None=None,db=Depends(get_db)):
    all_times=db.execute(select(PlantSnapshot.id,PlantSnapshot.at).order_by(PlantSnapshot.at,PlantSnapshot.id)).all()
    if not all_times:raise HTTPException(404,'Снимков пока нет')
    if at and at.tzinfo:raise HTTPException(422,'Передайте локальное виртуальное время без часового пояса')
    stmt=select(PlantSnapshot)
    if at:stmt=stmt.where(PlantSnapshot.at<=at)
    snap=db.scalar(stmt.order_by(PlantSnapshot.at.desc(),PlantSnapshot.id.desc()).limit(1))
    if not snap:raise HTTPException(404,'До этого времени снимков нет')
    return dict(at=snap.at.isoformat(),plant=plant_view(db,snap.state),available=[t.isoformat() for _,t in all_times],is_demo=True)
