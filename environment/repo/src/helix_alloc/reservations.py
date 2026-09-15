from __future__ import annotations

from helix_alloc.models import Order, Reservation


def reserved_lot_ids(order: Order, reservations: list[Reservation]) -> list[str]:
    return [row.lot_id for row in reservations if row.order_id == order.order_id]
