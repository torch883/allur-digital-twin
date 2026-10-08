import pytest
from sqlalchemy import select,func
from app.models import ProductionRecord,QualityRecord,Incident,PlantSnapshot

@pytest.mark.parametrize('path',['/','/docs','/openapi.json','/api/health','/api/plant','/api/stages/painting','/api/equipment/ABB-01','/api/kpi','/api/dashboard','/api/downtime','/api/quality','/api/incidents','/api/recommendations','/api/forecast/downtime','/api/forecast/plan','/api/forecast/bottleneck','/api/simulation','/api/timeline'])
def test_read_contracts(client,path):
    response=client.get(path)
    assert response.status_code==200,response.text
    if path.startswith('/api/'):assert isinstance(response.json(),dict)

def test_input_validation_and_error_format(client):
    for path,body in [('/api/simulation',{'enabled':True,'speed':7}),('/api/impact',{'defect_reduction_pct':101})]:
        response=client.post(path,json=body);assert response.status_code==422;assert 'error' in response.json()
    assert client.get('/api/kpi?from=2026-10-02&to=2026-10-01').status_code==422
    assert client.get('/api/stages/unknown').status_code==404
    assert client.get('/api/kpi?stage=unknown').status_code==404
    assert client.post('/api/scenarios/nope').status_code==422

def test_incident_transitions_and_filters(client):
    items=client.get('/api/incidents?severity=critical&stage=painting').json()['items']
    assert items and all(i['severity']=='critical' for i in items)
    id=items[0]['id'];assert client.post(f'/api/incidents/{id}/ack').json()['status']=='ack'
    assert client.post(f'/api/incidents/{id}/resolve').json()['status']=='resolved'
    assert client.post(f'/api/incidents/{id}/ack').status_code==409
    assert client.get('/api/incidents?from=2030-01-01').json()['items']==[]

def test_scenarios_cascade_and_reset_preserves_source(client,db):
    import app.main as main
    baseline=[(r.id,r.fact) for r in db.scalars(select(ProductionRecord)).all()]
    assert client.post('/api/scenarios/conveyor_failure').status_code==200
    sim=main.app.state.simulator;initial=sim.state['buffers'][1]['qty']
    for _ in range(20):sim.step(db,minutes=20,random_events=False)
    assert sim.state['buffers'][1]['qty']>initial
    assert sim.state['stages']['assembly']['load_pct']==0
    assert sim.state['stages']['painting']['load_pct']<1
    assert sim.state['stages']['welding']['load_pct']<20
    assert all(0<=b['qty']<=b['capacity'] for b in sim.state['buffers'])
    assert client.post('/api/scenarios/reset').status_code==200
    assert sim.state['scenario'] is None
    db.expire_all()
    assert [(r.id,r.fact) for r in db.scalars(select(ProductionRecord)).all()]==baseline
    assert db.scalar(select(func.count()).select_from(QualityRecord).where(QualityRecord.is_synthetic==False))==6

def test_supply_depletes_downstream_and_paint_scenario(client,db):
    import app.main as main
    client.post('/api/scenarios/supply_disruption');sim=main.app.state.simulator
    for _ in range(15):sim.step(db,minutes=20,random_events=False)
    assert sim.state['stages']['assembly']['load_pct']==0
    assert sim.state['inventory']['parts']==0
    client.post('/api/scenarios/paint_defect_spike')
    assert sim.state['stages']['painting']['defect_pct']==8

def test_timeline_is_actual_snapshot(client,db):
    import app.main as main
    before=client.get('/api/timeline').json()
    main.app.state.simulator.step(db,minutes=20,random_events=False)
    at=before['at'];historic=client.get('/api/timeline',params={'at':at}).json()
    assert historic['plant']['state']['stages']['assembly']['fact']==before['plant']['state']['stages']['assembly']['fact']
    assert client.get('/api/timeline?at=2020-01-01T00:00:00').status_code==404

def test_websocket_and_simulation(client):
    with client.websocket_connect('/ws/live') as ws:
        event=ws.receive_json();assert event['type']=='kpi_update';assert event['payload']['is_demo']
    assert client.post('/api/simulation',json={'enabled':False,'speed':20}).json()['speed']==20
    assert client.post('/api/forecast/refresh').status_code==200
    assert client.post('/api/impact',json={}).json()['annual_savings']>0
