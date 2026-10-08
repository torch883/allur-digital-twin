from fastapi import APIRouter,Request,Depends
from app.db import get_db
from app.services.views import bottleneck_view
router=APIRouter(prefix='/api/forecast',tags=['Прогноз'])

@router.get('/downtime')
def downtime(request:Request):
    f=request.app.state.forecast.cached
    return dict(items=f['risks'],disclaimer=f['disclaimer'],training=f['training'],updated_at=f['updated_at'],revision=f['revision'])

@router.get('/plan')
def plan(request:Request):return dict(**request.app.state.forecast.cached['plan'],disclaimer=request.app.state.forecast.cached['disclaimer'])

@router.get('/bottleneck')
def bottleneck(request:Request):return bottleneck_view(request.app.state.simulator.state)

@router.post('/refresh')
async def refresh(request:Request,db=Depends(get_db)):
    async with request.app.state.simulator.lock:
        result=request.app.state.forecast.refresh(db,request.app.state.simulator.state);db.commit()
    await request.app.state.hub.broadcast('forecast_update',{'revision':result['revision']})
    return result
