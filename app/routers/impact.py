from fastapi import APIRouter,Depends
from app.db import get_db
from app.schemas import ImpactInput
from app.services.impact_service import impact
router=APIRouter(prefix='/api',tags=['Бизнес-эффект'])

@router.post('/impact')
def calculate(body:ImpactInput,db=Depends(get_db)):return impact(db,body)
