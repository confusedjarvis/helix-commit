from __future__ import annotations

from datetime import datetime, timedelta, timezone

from helix_alloc.models import Destination, Lot


def utc_date(value: datetime):
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(timezone.utc).date()


def arrival_date(dest: Destination, commit_at: datetime):
    return utc_date(commit_at) + timedelta(days=dest.transit_days)


def meets_remaining_shelf_life(lot: Lot, dest: Destination, commit_at: datetime) -> bool:
    remaining = (lot.expiry - arrival_date(dest, commit_at)).days
    return remaining >= dest.min_remaining_days
