from datetime import datetime, date
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Stage(Base):
    __tablename__ = 'stages'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    order: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(20))

class Equipment(Base):
    __tablename__ = 'equipment'
    id: Mapped[int] = mapped_column(primary_key=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey('stages.id'))
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    critical: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default='running')
    last_maintenance_at: Mapped[datetime] = mapped_column(DateTime)
    mtbf_hours: Mapped[float] = mapped_column(Float)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)

class ProductionRecord(Base):
    __tablename__ = 'production_records'
    __table_args__ = (UniqueConstraint('date', 'shift', 'stage_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    shift: Mapped[int] = mapped_column(Integer, default=0)
    stage_id: Mapped[int] = mapped_column(ForeignKey('stages.id'))
    plan: Mapped[int] = mapped_column(Integer)
    fact: Mapped[int] = mapped_column(Integer)
    run_hours: Mapped[float] = mapped_column(Float)
    load_pct: Mapped[float] = mapped_column(Float)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

class DowntimeEvent(Base):
    __tablename__ = 'downtime_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey('equipment.id'))
    stage_id: Mapped[int] = mapped_column(ForeignKey('stages.id'))
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_min: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(250))
    kind: Mapped[str] = mapped_column(String(20))
    resolved: Mapped[bool] = mapped_column(Boolean, default=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    time_assumed: Mapped[bool] = mapped_column(Boolean, default=False)

class QualityRecord(Base):
    __tablename__ = 'quality_records'
    __table_args__ = (UniqueConstraint('date', 'stage_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey('stages.id'))
    produced: Mapped[int] = mapped_column(Integer)
    defects: Mapped[int] = mapped_column(Integer)
    defect_pct: Mapped[float] = mapped_column(Float)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

class MonthlyPlan(Base):
    __tablename__ = 'monthly_plans'
    __table_args__ = (UniqueConstraint('month', 'model'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7))
    model: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)

class Incident(Base):
    __tablename__ = 'incidents'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str] = mapped_column(String(250), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey('stages.id'), nullable=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey('equipment.id'), nullable=True)
    severity: Mapped[str] = mapped_column(String(20))
    type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default='open')
    source: Mapped[str] = mapped_column(String(20))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

class Recommendation(Base):
    __tablename__ = 'recommendations'
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey('incidents.id'), nullable=True, unique=True)
    stage_id: Mapped[int | None] = mapped_column(ForeignKey('stages.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(1000))
    expected_effect: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime)

class ScenarioRun(Base):
    __tablename__ = 'scenario_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class PlantSnapshot(Base):
    __tablename__ = 'plant_snapshots'
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, index=True)
    state: Mapped[dict] = mapped_column(JSON)

class Inventory(Base):
    __tablename__ = 'inventory'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[float] = mapped_column(Float)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
