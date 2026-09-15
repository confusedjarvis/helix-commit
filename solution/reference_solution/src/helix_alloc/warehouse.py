from __future__ import annotations

from datetime import datetime

from helix_alloc.models import Lot, QaEvent


def _replay(events: list[QaEvent], lot_id: str, at: datetime) -> tuple[bool, int]:
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
            held += int(getattr(event, "qty_mg", 0) or 0)
        elif event.type == "release_qty":
            held = max(0, held - int(getattr(event, "qty_mg", 0) or 0))
    return released, held


def lot_released(lot: Lot, events: list[QaEvent], at: datetime) -> bool:
    released, _held = _replay(events, lot.lot_id, at)
    return released


def open_hold_qty(lot_id: str, events: list[QaEvent], at: datetime) -> int:
    _released, held = _replay(events, lot_id, at)
    return held


def allocatable_mg(lot_id: str, remaining_mg: int, events: list[QaEvent], at: datetime) -> int:
    released, held = _replay(events, lot_id, at)
    if not released:
        return 0
    return max(0, remaining_mg - held)
