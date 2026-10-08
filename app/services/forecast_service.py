from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import roc_auc_score
from sqlalchemy import select
from app.models import Equipment, DowntimeEvent, ProductionRecord, QualityRecord, Stage
from app.services.rules_engine import ensure_incident

DISCLAIMER='Демонстрационная модель на синтетической истории. В промышленной версии — обучение на потоковых данных MES/SCADA.'
FEATURES=['Отказы за 7 дней','Отказы за 30 дней','Простой за 7 дней, мин','Остаток лимита, мин','Часы после ТО','Загрузка, %','Возраст / MTBF','Брак участка, %']

class ForecastService:
    def __init__(self):
        self.model=None;self.cached={};self.training={};self.cache_revision=0

    def _load(self,db):
        self.equipment=db.scalars(select(Equipment)).all()
        self.stages={s.id:s for s in db.scalars(select(Stage)).all()}
        self.down=defaultdict(list)
        for d in db.scalars(select(DowntimeEvent).where(DowntimeEvent.kind=='unplanned')).all(): self.down[d.equipment_id].append(d)
        self.prod={(p.stage_id,p.date):p for p in db.scalars(select(ProductionRecord)).all()}
        self.qual={(q.stage_id,q.date):q for q in db.scalars(select(QualityRecord)).all()}

    def features(self,eq,at,live=None):
        # At start of prediction day: only strictly earlier events/features.
        prior=[d for d in self.down[eq.id] if d.started_at<at]
        d7=[d for d in prior if d.started_at>=at-timedelta(days=7)]
        d30=[d for d in prior if d.started_at>=at-timedelta(days=30)]
        yesterday=(at-timedelta(days=1)).date()
        p=self.prod.get((eq.stage_id,yesterday));q=self.qual.get((eq.stage_id,yesterday))
        hours=max(0,(at-eq.last_maintenance_at).total_seconds()/3600)
        code=self.stages[eq.stage_id].code
        l=(live or {}).get('stages',{}).get(code,{})
        recent=sum(d.duration_min for d in prior if d.started_at>=at-timedelta(days=1))
        return [len(d7),len(d30),sum(d.duration_min for d in d7),max(0,60-max(recent,l.get('downtime_min',0))),hours,l.get('load_pct',p.load_pct if p else 90),hours/eq.mtbf_hours,l.get('defect_pct',q.defect_pct if q else 1)]

    def train(self,db):
        self._load(db);rows=[];labels=[];days=[]
        dates=sorted({p.date for p in self.prod.values()})
        for day in dates[7:]:
            at=datetime.combine(day,datetime.min.time())
            for eq in self.equipment:
                if self.stages[eq.stage_id].type!='production':continue
                rows.append(self.features(eq,at));labels.append(int(any(at<=d.started_at<at+timedelta(days=1) for d in self.down[eq.id])));days.append(day)
        X=np.asarray(rows,dtype=float);y=np.asarray(labels)
        cutoff=sorted(set(days))[int(len(set(days))*.8)]
        mask=np.array([d<cutoff for d in days])
        model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,random_state=42))
        auc=None
        if len(np.unique(y[mask]))==2 and len(np.unique(y[~mask]))==2:
            model.fit(X[mask],y[mask]);auc=float(roc_auc_score(y[~mask],model.predict_proba(X[~mask])[:,1]))
        if len(np.unique(y))<2: raise ValueError('Обучению нужны оба класса')
        self.model=model.fit(X,y)
        self.training=dict(rows=len(y),positive_events=int(y.sum()),synthetic_days=60,case_days=2,validation='Последние 20% дат; временное разделение, без случайного перемешивания',holdout_auc=round(auc,3) if auc is not None else None,probability_note='Оценки не откалиброваны на реальном заводе. AUC характеризует только синтетический эксперимент.')

    def refresh(self,db,live=None):
        if self.model is None:self.train(db)
        else:self._load(db)
        at=datetime.fromisoformat(live['at']) if live else datetime(2026,10,3)
        scaler=self.model.named_steps['standardscaler'];coef=self.model.named_steps['logisticregression'].coef_[0]
        risks=[]
        for eq in self.equipment:
            values=np.asarray([self.features(eq,at,live)],dtype=float)
            p=float(self.model.predict_proba(values)[0,1]);contrib=scaler.transform(values)[0]*coef
            factors=[dict(name=FEATURES[int(i)],value=round(float(values[0,i]),2),contribution=round(float(contrib[i]),3),direction='повышает' if contrib[i]>0 else 'снижает') for i in np.argsort(np.abs(contrib))[::-1][:3]]
            risks.append(dict(equipment=eq.code,stage=self.stages[eq.stage_id].code,probability=round(p,4),risk_level='critical' if p>.4 else ('warning' if p>.18 else 'normal'),factors=factors,is_demo=True,currently_down=(live or {}).get('equipment_status',{}).get(eq.code)=='down',action=f'Проверить {eq.code}: {factors[0]["name"].lower()}',expected_effect='Проверить ведущий фактор риска; величина предотвращённого простоя не подтверждена'))
        assembly=next(s.id for s in self.stages.values() if s.code=='assembly')
        records=sorted([p for p in self.prod.values() if p.stage_id==assembly],key=lambda p:p.date)[-21:]
        series=pd.Series([r.fact for r in records],dtype=float)
        X=np.arange(len(series)).reshape(-1,1);reg=LinearRegression().fit(X,series.to_numpy())
        residual=series.to_numpy()-reg.predict(X)
        rng=np.random.default_rng(42)
        predicted=np.clip(reg.predict(np.arange(len(series),len(series)+21).reshape(-1,1)),0,320)
        scenario=(live or {}).get('scenario')
        multiplier={'conveyor_failure':.75,'supply_disruption':.7,'paint_defect_spike':.94}.get(scenario,1)
        samples=240+np.clip(predicted[None,:]+rng.choice(residual,(1000,21),replace=True),0,320).sum(axis=1)*multiplier
        p10,p50,p90=[int(x) for x in np.quantile(samples,[.1,.5,.9])]
        plan=dict(p10=p10,p50=p50,p90=p90,target=5500,risk_pct=round(float(np.mean(samples<5500))*100,1),as_of='2026-10-02',is_synthetic=True,
            assumptions=['23 рабочих дня в месяце, 2 дня учтены, остаётся 21.','Линейная регрессия по 21 дню смешанной истории; бутстрэп остатков, 1000 траекторий.','Синтетическая история имеет план 240/сутки, исходные строки — 120; прогноз чувствителен к этому расхождению.',f'Сценарный коэффициент оставшегося выпуска: {multiplier:.2f}; заданное допущение, не оценка ML.'],
            history=[dict(date=str(r.date),fact=r.fact,is_synthetic=r.is_synthetic) for r in records])
        if p50<5500:
            ensure_incident(db,key=f'forecast:plan:{scenario or "baseline"}',stage_id=assembly,severity='warning',type='forecast',source='ai',title=f'Демо-прогноз: риск недовыполнения плана',description=f'p50 {p50} из 5500. Смешанная история и допущения; не производственный прогноз.',at=at,is_demo=True,action='Согласовать период плана и оценить доступную мощность сборки',effect='Проверить план выпуска и сценарии восстановления')
        self.cache_revision+=1
        self.cached=dict(risks=sorted(risks,key=lambda x:x['probability'],reverse=True),plan=plan,disclaimer=DISCLAIMER,training=self.training,updated_at=at.isoformat(),revision=self.cache_revision)
        return self.cached

    def anomalies(self,db,live):
        for code,current in live['stages'].items():
            stage=next((s for s in self.stages.values() if s.code==code),None)
            if not stage or stage.type!='production':continue
            q=sorted([q for q in self.qual.values() if q.stage_id==stage.id],key=lambda q:q.date)[-14:]
            for metric,values,value in [('quality',[q.defect_pct for q in q],current['defect_pct']),('throughput',[p.load_pct for p in sorted(self.prod.values(),key=lambda p:p.date) if p.stage_id==stage.id][-14:],current['load_pct'])]:
                if not values:continue
                z=(value-float(np.mean(values)))/max(float(np.std(values)),.75)
                if abs(z)>3:
                    ensure_incident(db,key=f'ai:anomaly:{code}:{metric}:{live["scenario"] or "baseline"}',stage_id=stage.id,type=metric,severity='warning',source='ai',title=f'{stage.name}: аномалия '+('качества' if metric=='quality' else 'загрузки'),description=f'z-score {z:.1f} по предыдущим 14 дням. История смешанная, сигнал демонстрационный.',at=datetime.fromisoformat(live['at']),is_demo=True)
