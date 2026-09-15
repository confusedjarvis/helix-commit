from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


FillPolicy = Literal["ship_complete", "allow_partial"]
QaType = Literal["quarantine", "release", "hold_qty", "release_qty"]


def parse_dt(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


@dataclass(frozen=True)
class Lot:
    lot_id: str
    sku: str
    qty_mg: int
    expiry: date
    received_at: datetime
    temp_class: str
    qa_status: str


@dataclass(frozen=True)
class QaEvent:
    lot_id: str
    ts: datetime
    type: QaType
    reason: str
    seq: int
    qty_mg: int = 0


@dataclass(frozen=True)
class Destination:
    dest_id: str
    name: str
    transit_days: int
    min_remaining_days: int
    temp_class: str


@dataclass(frozen=True)
class Order:
    order_id: str
    dest_id: str
    sku: str
    qty_mg: int
    fill_policy: FillPolicy


@dataclass(frozen=True)
class Reservation:
    order_id: str
    lot_id: str
    qty_mg: int
    reserved_at: datetime


@dataclass(frozen=True)
class AllocationLine:
    order_id: str
    lot_id: str
    sku: str
    qty_mg: int


@dataclass
class OrderResult:
    order_id: str
    status: Literal["committed", "backordered", "blocked"]
    lines: list[AllocationLine] = field(default_factory=list)
    backorder_mg: int = 0
    reason: str | None = None


@dataclass
class RunResult:
    commit_at: datetime
    orders: list[OrderResult]
    inventory: dict[str, int]
