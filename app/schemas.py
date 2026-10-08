from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class SimulationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    speed: Literal[1, 5, 20] = 1

class ImpactInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    downtime_reduction_pct: float = Field(default=20, ge=0, le=100)
    defect_reduction_pct: float = Field(default=25, ge=0, le=100)
    downtime_cost_per_hour: float = Field(default=150000, ge=0, le=1e9)
    defect_cost_per_car: float = Field(default=80000, ge=0, le=1e9)
    implementation_cost: float = Field(default=15000000, ge=0, le=1e12)
    operating_days_per_year: int = Field(default=250, ge=1, le=366)
