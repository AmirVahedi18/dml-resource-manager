from typing import Literal

from pydantic import BaseModel


class RankedUsageOut(BaseModel):
    metric: Literal["gpu_hours", "ram_gb_hours"]
    unit: str
    labels: list[str]
    values: list[float]
