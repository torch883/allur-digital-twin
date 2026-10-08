from datetime import date
import pytest
from sqlalchemy import select,func
from app.models import ProductionRecord,QualityRecord,MonthlyPlan,Stage
from app.seed.seed import seed
from app.services.kpi_service import calculate_kpi,kpis,monthly_plan
from app.services.impact_service import impact
from app.schemas import ImpactInput

def test_welding_manual_oee():
    result=calculate_kpi(120,118,7.8,1,118,2)
    # A=7.8/16=.4875; P=118/120; Q=116/118; product=.47125.
    assert result['availability']==48.75
    assert result['oee']==pytest.approx(47.125,abs=.01)
    assert result['good']==116

def test_case_aggregates_and_no_double_count(db):
    result=kpis(db)
    assert result['final_output']==240
    assert result['final_good']==237
    paint=next(x for x in result['stages'] if x['code']=='painting')
    assert paint['fact']==231
    assert paint['defect_pct']==pytest.approx(10/231*100,abs=.001)
    assert result['downtime_min']==150
    assert not any(x['is_synthetic'] for x in result['stages'])

def test_missing_data_safe(db):
    result=kpis(db,date(2030,1,1),date(2030,1,2))
    assert result['plant_oee'] is None
    assert all(not s['has_data'] for s in result['stages'])
    assert calculate_kpi(0,0,0,0,0,0)['oee']==0

def test_seed_idempotent_and_case_unchanged(db):
    before=db.scalar(select(func.count()).select_from(ProductionRecord));seed(db)
    assert db.scalar(select(func.count()).select_from(ProductionRecord))==before==186
    real=db.scalars(select(ProductionRecord).where(ProductionRecord.is_synthetic==False)).all()
    assert len(real)==6
    assert sum(r.fact for r in real)==700
    assert len({r.date for r in db.scalars(select(ProductionRecord).where(ProductionRecord.is_synthetic==True)).all()})==60

def test_plan_flags_and_unknown_model_actual(db):
    m=monthly_plan(db)
    assert (m['models_total'],m['target'],m['actual'])==(4800,5500,240)
    assert m['data_warning']
    assert all(x['actual'] is None for x in m['models'])

def test_impact_excludes_planned_and_zero_savings(db):
    result=impact(db,ImpactInput())
    assert result['baseline']['unplanned_equipment_minutes']==120
    assert result['baseline']['stage_defect_events']==18
    assert result['annual_savings']==52500000
    assert impact(db,ImpactInput(downtime_reduction_pct=0,defect_reduction_pct=0))['payback_months'] is None
