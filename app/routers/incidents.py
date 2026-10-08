from datetime import date,datetime,timedelta
from typing import Literal
from fastapi import APIRouter,Depends,Query,HTTPException
from sqlalchemy import select
from app.db import get_db
from app.models import Incident,Recommendation
from app.services.views import incident_dict,row_dict,stage_or_404
from app.routers.kpi import check_dates
router=APIRouter(prefix='/api',tags=['Инциденты'])

@router.get('/incidents')
def incidents(severity:Literal['info','warning','critical']|None=None,stage:str|None=None,status:Literal['open','ack','resolved']|None=None,start:date|None=Query(None,alias='from'),end:date|None=Query(None,alias='to'),db=Depends(get_db)):
    stmt=select(Incident)
    if severity:stmt=stmt.where(Incident.severity==severity)
    if status:stmt=stmt.where(Incident.status==status)
    if stage:stmt=stmt.where(Incident.stage_id==stage_or_404(db,stage).id)
    if start:stmt=stmt.where(Incident.created_at>=datetime.combine(start,datetime.min.time()))
    if end:stmt=stmt.where(Incident.created_at<datetime.combine(end+timedelta(days=1),datetime.min.time()))
    if start and end:check_dates(start,end)
    return dict(items=[incident_dict(db,i) for i in db.scalars(stmt.order_by(Incident.created_at.desc(),Incident.id.desc())).all()])

def transition(db,id,status):
    i=db.get(Incident,id)
    if not i:raise HTTPException(404,'Инцидент не найден')
    if i.status=='resolved' and status=='ack':raise HTTPException(409,'Закрытый инцидент нельзя принять в работу')
    i.status=status;db.commit();return incident_dict(db,i)

@router.post('/incidents/{id}/ack')
def ack(id:int,db=Depends(get_db)):return transition(db,id,'ack')

@router.post('/incidents/{id}/resolve')
def resolve(id:int,db=Depends(get_db)):return transition(db,id,'resolved')

@router.get('/recommendations')
def recommendations(db=Depends(get_db)):
    rows=db.scalars(select(Recommendation).join(Incident,Recommendation.incident_id==Incident.id).where(Incident.status!='resolved').order_by(Recommendation.created_at.desc())).all()
    return dict(items=[row_dict(r) for r in rows])
