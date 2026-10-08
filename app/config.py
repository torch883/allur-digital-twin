import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('DATABASE_URL', f'sqlite:///{ROOT / "data" / "allur.db"}')
    tick_seconds: float = float(os.getenv('TICK_SECONDS', '2.5'))
    simulation_enabled: bool = os.getenv('SIMULATION_ENABLED', 'true').lower() == 'true'
    forecast_every_ticks: int = 12
    oee_target: float = 85
    defect_limit: float = 2
    downtime_limit: float = 60
    monthly_target: int = 5500
    planned_daily_hours: int = 16
    seed: int = 42

settings = Settings()
