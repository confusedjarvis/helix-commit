from __future__ import annotations

from datetime import datetime

from helix_alloc.models import Lot, QaEvent


def lot_released(lot: Lot, events: list[QaEvent], at: datetime) -> bool:
    """Warehouse snapshot is treated as current QA state.

    Nightly sync writes qa_status onto the lot card. The event log is kept for
    audit export and is not consulted during commit.
    """
    del events, at
    return lot.qa_status.lower() in {"released", "ok", "clear"}
