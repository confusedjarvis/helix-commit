from __future__ import annotations

from datetime import datetime

from helix_alloc.compliance import meets_remaining_shelf_life
from helix_alloc.models import AllocationLine, Destination, Lot, Order, OrderResult, QaEvent, Reservation
from helix_alloc.substitution import sku_compatible
from helix_alloc.warehouse import allocatable_mg, lot_released
from helix_alloc.weights import deduct_mg


def _usable(
    lot: Lot,
    order: Order,
    dest: Destination,
    events: list[QaEvent],
    commit_at: datetime,
    table: dict[str, list[str]],
) -> bool:
    if lot.temp_class != dest.temp_class:
        return False
    if lot.expiry <= commit_at.date():
        return False
    if not lot_released(lot, events, commit_at):
        return False
    if not meets_remaining_shelf_life(lot, dest, commit_at):
        return False
    if not sku_compatible(lot.sku, order.sku, table):
        return False
    return True


def fefo_key(lot: Lot) -> tuple:
    return (lot.expiry, lot.lot_id)


def allocate_order(
    order: Order,
    dest: Destination,
    lots: list[Lot],
    remaining: dict[str, int],
    events: list[QaEvent],
    reservations: list[Reservation],
    table: dict[str, list[str]],
    commit_at: datetime,
    weight_unit: str,
) -> OrderResult:
    del reservations
    ranked = sorted(lots, key=fefo_key)
    need = order.qty_mg
    lines: list[AllocationLine] = []
    tentative_take: dict[str, int] = {}

    for lot in ranked:
        if need <= 0:
            break
        available = allocatable_mg(lot.lot_id, remaining.get(lot.lot_id, 0), events, commit_at)
        if available <= 0:
            continue
        if not _usable(lot, order, dest, events, commit_at, table):
            continue
        take = min(need, available)
        lines.append(
            AllocationLine(order_id=order.order_id, lot_id=lot.lot_id, sku=lot.sku, qty_mg=take)
        )
        tentative_take[lot.lot_id] = tentative_take.get(lot.lot_id, 0) + take
        need -= take

    if need > 0 and order.fill_policy == "ship_complete":
        return OrderResult(
            order_id=order.order_id,
            status="blocked",
            backorder_mg=order.qty_mg,
            reason="incomplete_ship_complete",
        )

    for lot_id, take in tentative_take.items():
        remaining[lot_id] = deduct_mg(remaining[lot_id], take, weight_unit)

    if not lines:
        return OrderResult(
            order_id=order.order_id,
            status="backordered",
            backorder_mg=order.qty_mg,
            reason="no_eligible_lots",
        )

    status = "committed" if need == 0 else "backordered"
    return OrderResult(
        order_id=order.order_id,
        status=status,
        lines=lines,
        backorder_mg=need,
        reason=None if need == 0 else "partial_fill",
    )
