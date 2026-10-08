from sqlalchemy import select
from app.models import DowntimeEvent, QualityRecord, Stage

def impact(db, inputs):
    downtime=sum(db.scalars(select(DowntimeEvent.duration_min).where(DowntimeEvent.is_synthetic==False,DowntimeEvent.is_demo==False,DowntimeEvent.kind=='unplanned')).all())
    # Stage defects represent processing/rework events, never unique finished cars.
    defects=sum(db.scalars(select(QualityRecord.defects).where(QualityRecord.is_synthetic==False)).all())
    hours=downtime/60/2*inputs.operating_days_per_year
    annual_defects=defects/2*inputs.operating_days_per_year
    downtime_saving=hours*inputs.downtime_reduction_pct/100*inputs.downtime_cost_per_hour
    quality_saving=annual_defects*inputs.defect_reduction_pct/100*inputs.defect_cost_per_car
    total=downtime_saving+quality_saving
    return dict(annual_savings=round(total),downtime_savings=round(downtime_saving),quality_savings=round(quality_saving),
        payback_months=round(inputs.implementation_cost/total*12,1) if total>0 else None,currency='KZT',inputs=inputs.model_dump(),
        baseline=dict(observed_days=2,unplanned_equipment_minutes=downtime,planned_minutes_excluded=30,stage_defect_events=defects,annualized_equipment_hours=hours,annualized_defect_events=annual_defects),
        assumptions=['Все цены и ожидаемые улучшения — допущения, не данные АЛЛЮР.',f'Два дня экстраполированы на {inputs.operating_days_per_year} рабочих дней; сезонность не учтена.',
        '120 минут — сумма неплановых простоев оборудования, не длительность остановки завода. Стоимость часа относится к оборудованию.',
        '18 дефектов — события на трёх переделах, не 18 уникальных автомобилей. Цена брака трактуется как затраты на один дефект/исправление.',
        'Плановое ТО исключено из эффекта сокращения аварий. Экономия от брака и простоев предполагается независимой.',
        'Простая окупаемость без дисконтирования, эксплуатационных расходов и налогов; требуется проверка на реальных данных.'],
        curve=[dict(reduction_pct=p,annual_savings=round(hours*p/100*inputs.downtime_cost_per_hour+quality_saving)) for p in range(0,101,10)])
