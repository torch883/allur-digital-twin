from datetime import date,datetime,timedelta
from collections import defaultdict
from fastapi import APIRouter,Depends,Query
from sqlalchemy import select
from app.db import get_db
from app.models import DowntimeEvent,Equipment
from app.services.views import row_dict,stage_or_404
from app.services.kpi_service import CASE_START,CASE_END
from app.routers.kpi import check_dates
router=APIRouter(prefix='/api',tags=['Простои'])

@router.get('/downtime')
def downtime(start:date=Query(CASE_START,alias='from'),end:date=Query(CASE_END,alias='to'),stage:str|None=None,db=Depends(get_db)):
    check_dates(start,end)
    stmt=select(DowntimeEvent).where(DowntimeEvent.started_at>=datetime.combine(start,datetime.min.time()),DowntimeEvent.started_at<datetime.combine(end+timedelta(days=1),datetime.min.time()))
    if stage:stmt=stmt.where(DowntimeEvent.stage_id==stage_or_404(db,stage).id)
    rows=db.scalars(stmt.order_by(DowntimeEvent.started_at.desc())).all();reasons=defaultdict(float);equipment=defaultdict(float);items=[]
    for x in rows:
        e=db.get(Equipment,x.equipment_id);item=row_dict(x);item['equipment']=e.code;items.append(item);reasons[x.reason]+=x.duration_min;equipment[e.code]+=x.duration_min
    return dict(items=items,total_minutes=sum(x.duration_min for x in rows),by_reason=dict(reasons),by_equipment=dict(equipment),note='Сумма минут оборудования, не длительность остановки завода')
