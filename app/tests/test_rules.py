from sqlalchemy import select,func
from app.models import Incident,Recommendation
from app.services.rules_engine import evaluate_historical,quality_severity,downtime_severity

def test_paint_is_critical_and_planned_not_incident(db):
    evaluate_historical(db);db.commit()
    incidents=db.scalars(select(Incident)).all()
    assert any(i.severity=='critical' and '5.17%' in i.title for i in incidents)
    assert any('Конвейер-03' in i.title and i.severity=='warning' for i in incidents)
    assert not any('Плановое ТО' in i.title or i.event_key.startswith('downtime:4:') for i in incidents)

def test_idempotent_rules(db):
    evaluate_historical(db);db.commit()
    before=db.scalar(select(func.count()).select_from(Incident))
    evaluate_historical(db);db.commit()
    assert db.scalar(select(func.count()).select_from(Incident))==before
    assert db.scalar(select(func.count()).select_from(Recommendation))==before

def test_threshold_boundaries():
    assert quality_severity(2) is None
    assert quality_severity(4)=='warning'
    assert quality_severity(4.01)=='critical'
    assert downtime_severity(49,True) is None
    assert downtime_severity(50,True)=='warning'
    assert downtime_severity(60,True)=='warning'
    assert downtime_severity(61,True)=='critical'
    assert downtime_severity(100,False) is None
