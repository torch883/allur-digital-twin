from datetime import date
from collections import defaultdict
from fastapi import APIRouter,Depends,Query,Request,HTTPException
from sqlalchemy import select
from app.db import get_db
from app.services.kpi_service import kpis,monthly_plan,CASE_START,CASE_END
from app.services.views import incident_dict,stage_or_404,bottleneck_view
from app.models import Incident,DowntimeEvent

router=APIRouter(prefix='/api',tags=['KPI'])

def check_dates(start,end):
    if start>end:raise HTTPException(422,'Начальная дата позже конечной')

@router.get('/kpi')
def kpi(start:date=Query(CASE_START,alias='from'),end:date=Query(CASE_END,alias='to'),stage:str|None=None,db=Depends(get_db)):
    check_dates(start,end)
    if stage:stage_or_404(db,stage)
    return kpis(db,start,end,stage)

@router.get('/dashboard')
def dashboard(request:Request,db=Depends(get_db)):
    incidents=db.scalars(select(Incident).where(Incident.status!='resolved').order_by(Incident.created_at.desc())).all()
    reasons=defaultdict(float)
    for d in db.scalars(select(DowntimeEvent).where(DowntimeEvent.is_synthetic==False,DowntimeEvent.is_demo==False)).all():reasons[d.reason]+=d.duration_min
    return dict(kpi=kpis(db),monthly_plan=monthly_plan(db),top_downtime=[dict(reason=r,minutes=m) for r,m in sorted(reasons.items(),key=lambda x:-x[1])],
        decisions=[incident_dict(db,i) for i in sorted(incidents,key=lambda x:({'critical':0,'warning':1,'info':2}[x.severity],-x.id))[:6]],
        active_incidents=len(incidents),bottleneck=bottleneck_view(request.app.state.simulator.state),live=request.app.state.simulator.state)
