from __future__ import annotations

from datetime import datetime

from helix_alloc.models import Destination, Lot


DEFAULT_SHELF_DAYS = 14


def meets_remaining_shelf_life(lot: Lot, dest: Destination, commit_at: datetime) -> bool:
    """Domestic DC rule: lot must still have two weeks at ship time.

    Destination-specific transit and bonded-warehouse floors were added to the
    compliance service later; this client still uses the original ship-date check.
    """
    del dest
    remaining = (lot.expiry - commit_at.date()).days
    return remaining >= DEFAULT_SHELF_DAYS
