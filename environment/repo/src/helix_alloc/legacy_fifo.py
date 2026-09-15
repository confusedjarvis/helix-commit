from __future__ import annotations

from helix_alloc.models import Lot


def fifo_key(lot: Lot) -> tuple:
    return (lot.received_at, lot.lot_id)
