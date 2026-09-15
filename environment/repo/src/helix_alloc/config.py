from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from helix_alloc.models import parse_dt


@dataclass(frozen=True)
class RuntimeConfig:
    commit_at: datetime
    allocation_strategy: str
    weight_unit: str


def load_runtime(path: Path) -> RuntimeConfig:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return RuntimeConfig(
        commit_at=parse_dt(data["commit_at"]),
        allocation_strategy=str(data.get("allocation_strategy", "fifo")),
        weight_unit=str(data.get("weight_unit", "kg")),
    )
