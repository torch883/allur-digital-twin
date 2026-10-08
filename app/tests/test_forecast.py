from datetime import datetime
from app.services.forecast_service import ForecastService

def test_real_model_ranges_factors_and_ordered_quantiles(db):
    f=ForecastService();f.train(db);result=f.refresh(db)
    assert f.model is not None
    assert result['training']['rows']>500
    assert len(result['risks'])==12
    assert all(0<=r['probability']<=1 for r in result['risks'])
    assert all(len(r['factors'])==3 for r in result['risks'])
    assert result['plan']['p10']<=result['plan']['p50']<=result['plan']['p90']
    assert result['disclaimer']

def test_features_use_only_prior_events(db):
    f=ForecastService();f.train(db)
    eq=next(x for x in f.equipment if x.code=='Конвейер-03')
    at=datetime(2026,10,2)
    features=f.features(eq,at)
    expected=[d for d in f.down[eq.id] if datetime(2026,9,25)<=d.started_at<at]
    assert features[0]==len(expected)
    assert features[2]==sum(d.duration_min for d in expected)
