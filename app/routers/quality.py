from datetime import date
from fastapi import APIRouter,Depends,Query
from sqlalchemy import select
from app.db import get_db
from app.models import QualityRecord,Stage
from app.services.views import row_dict,stage_or_404
from app.services.kpi_service import CASE_START,CASE_END
from app.routers.kpi import check_dates
router=APIRouter(prefix='/api',tags=['Качество'])

@router.get('/quality')
def quality(start:date=Query(CASE_START,alias='from'),end:date=Query(CASE_END,alias='to'),stage:str|None=None,db=Depends(get_db)):
    check_dates(start,end);stmt=select(QualityRecord).where(QualityRecord.date.between(start,end))
    if stage:stmt=stmt.where(QualityRecord.stage_id==stage_or_404(db,stage).id)
    items=[]
    for x in db.scalars(stmt.order_by(QualityRecord.date)).all():
        s=db.get(Stage,x.stage_id);r=row_dict(x);r.update(stage=s.code,stage_name=s.name,calculated_pct=round(x.defects/x.produced*100,3) if x.produced else 0);items.append(r)
    return dict(items=items,limit=2)
