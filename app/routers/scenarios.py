from typing import Literal
from fastapi import APIRouter,Request,Depends
from app.db import get_db
from app.schemas import SimulationInput
router=APIRouter(prefix='/api',tags=['Симуляция'])

@router.post('/scenarios/{name}')
async def scenario(name:Literal['conveyor_failure','paint_defect_spike','supply_disruption','reset'],request:Request,db=Depends(get_db)):
    sim=request.app.state.simulator
    async with sim.lock:state=sim.apply_scenario(db,name)
    await request.app.state.hub.broadcast('scenario',state)
    await request.app.state.hub.broadcast('equipment_status',state['equipment_status'])
    await request.app.state.hub.broadcast('forecast_update',{'revision':request.app.state.forecast.cache_revision})
    return dict(ok=True,name=name,state=state)

@router.get('/simulation')
def get_simulation(request:Request):
    s=request.app.state.simulator;return dict(enabled=s.enabled,speed=s.speed,virtual_time=s.state['at'],scenario=s.state['scenario'])

@router.post('/simulation')
async def simulation(body:SimulationInput,request:Request):
    s=request.app.state.simulator
    async with s.lock:s.enabled=body.enabled;s.speed=body.speed
    return get_simulation(request)
