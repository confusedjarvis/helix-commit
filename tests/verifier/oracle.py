"""Independent policy engine. Does not import agent code."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def _dt(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _date(value: str) -> date:
    return date.fromisoformat(value[:10])


@dataclass(frozen=True)
class Lot:
    lot_id: str
    sku: str
    qty_mg: int
    expiry: date
    temp_class: str


@dataclass(frozen=True)
class Event:
    lot_id: str
    ts: datetime
    type: str
    seq: int
    qty_mg: int = 0


@dataclass(frozen=True)
class Dest:
    dest_id: str
    transit_days: int
    min_remaining_days: int
    temp_class: str


@dataclass(frozen=True)
class Order:
    order_id: str
    dest_id: str
    sku: str
    qty_mg: int
    fill_policy: str


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def qa_replay(events: list[Event], lot_id: str, at: datetime) -> tuple[bool, int]:
    """Return (not_quarantined, open_hold_qty) after (ts, seq) replay."""
    relevant = [event for event in events if event.lot_id == lot_id and event.ts <= at]
    relevant.sort(key=lambda event: (event.ts, event.seq))
    released = True
    held = 0
    for event in relevant:
        if event.type == "quarantine":
            released = False
        elif event.type == "release":
            released = True
        elif event.type == "hold_qty":
            held += event.qty_mg
        elif event.type == "release_qty":
            held = max(0, held - event.qty_mg)
    return released, held


def qa_clear(events: list[Event], lot_id: str, at: datetime) -> bool:
    released, _held = qa_replay(events, lot_id, at)
    return released


def allocatable_mg(remaining_mg: int, events: list[Event], lot_id: str, at: datetime) -> int:
    released, held = qa_replay(events, lot_id, at)
    if not released:
        return 0
    return max(0, remaining_mg - held)


def sku_fit(lot_sku: str, order_sku: str, table: dict[str, list[str]]) -> bool:
    return lot_sku == order_sku or order_sku in table.get(lot_sku, [])


def eligible(lot: Lot, order: Order, dest: Dest, events: list[Event], table: dict[str, list[str]], at: datetime) -> bool:
    if lot.temp_class != dest.temp_class:
        return False
    if lot.expiry <= at.date():
        return False
    arrival = at.date() + timedelta(days=dest.transit_days)
    if (lot.expiry - arrival).days < dest.min_remaining_days:
        return False
    if not qa_clear(events, lot.lot_id, at):
        return False
    return sku_fit(lot.sku, order.sku, table)


def expected_from_data_dir(data_dir: Path, commit_at: datetime) -> dict[str, Any]:
    lots = [
        Lot(row["lot_id"], row["sku"], int(row["qty_mg"]), _date(row["expiry"]), row["temp_class"])
        for row in _load(data_dir / "warehouse" / "lots.json")
    ]
    events = [
        Event(
            row["lot_id"],
            _dt(row["ts"]),
            row["type"],
            int(row.get("seq", 0)),
            int(row.get("qty_mg", 0)),
        )
        for row in _load(data_dir / "warehouse" / "qa_events.json")
    ]
    dests = {
        row["dest_id"]: Dest(
            row["dest_id"],
            int(row["transit_days"]),
            int(row["min_remaining_days"]),
            row["temp_class"],
        )
        for row in _load(data_dir / "compliance" / "destinations.json")
    }
    table = {
        row["warehouse_sku"]: list(row["accepted_by_customer_skus"])
        for row in _load(data_dir / "compliance" / "substitutions.json")
    }
    orders = [
        Order(row["order_id"], row["dest_id"], row["sku"], int(row["qty_mg"]), row["fill_policy"])
        for row in _load(data_dir / "oms" / "orders.json")
    ]
    orders.sort(key=lambda item: item.order_id)
    remaining = {lot.lot_id: lot.qty_mg for lot in lots}
    lot_by_id = {lot.lot_id: lot for lot in lots}

    out_orders = []
    for order in orders:
        dest = dests[order.dest_id]
        ranked = sorted(lots, key=lambda lot: (lot.expiry, lot.lot_id))
        need = order.qty_mg
        lines = []
        tentative: dict[str, int] = {}
        for lot in ranked:
            if need <= 0:
                break
            if not eligible(lot, order, dest, events, table, commit_at):
                continue
            available = allocatable_mg(remaining[lot.lot_id], events, lot.lot_id, commit_at)
            if available <= 0:
                continue
            take = min(need, available)
            lines.append(
                {
                    "order_id": order.order_id,
                    "lot_id": lot.lot_id,
                    "sku": lot.sku,
                    "qty_mg": take,
                }
            )
            tentative[lot.lot_id] = tentative.get(lot.lot_id, 0) + take
            need -= take
        if need > 0 and order.fill_policy == "ship_complete":
            out_orders.append(
                {
                    "order_id": order.order_id,
                    "status": "blocked",
                    "backorder_mg": order.qty_mg,
                    "reason": "incomplete_ship_complete",
                    "lines": [],
                }
            )
            continue
        for lot_id, take in tentative.items():
            remaining[lot_id] -= take
        if not lines:
            out_orders.append(
                {
                    "order_id": order.order_id,
                    "status": "backordered",
                    "backorder_mg": order.qty_mg,
                    "reason": "no_eligible_lots",
                    "lines": [],
                }
            )
            continue
        out_orders.append(
            {
                "order_id": order.order_id,
                "status": "committed" if need == 0 else "backordered",
                "backorder_mg": need,
                "reason": None if need == 0 else "partial_fill",
                "lines": lines,
            }
        )

    del lot_by_id
    return {
        "commit_at": commit_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "orders": out_orders,
        "inventory": {
            "lots": [
                {"lot_id": lot_id, "remaining_mg": qty}
                for lot_id, qty in sorted(remaining.items())
            ]
        },
    }
