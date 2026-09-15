from __future__ import annotations

from pathlib import Path

from helix_alloc.io_util import read_json
from helix_alloc.models import Destination, Lot, Order, QaEvent, Reservation, parse_date, parse_dt


def load_lots(data_dir: Path) -> list[Lot]:
    rows = read_json(data_dir / "warehouse" / "lots.json")
    return [
        Lot(
            lot_id=row["lot_id"],
            sku=row["sku"],
            qty_mg=int(row["qty_mg"]),
            expiry=parse_date(row["expiry"]),
            received_at=parse_dt(row["received_at"]),
            temp_class=row["temp_class"],
            qa_status=row.get("qa_status", "released"),
        )
        for row in rows
    ]


def load_qa_events(data_dir: Path) -> list[QaEvent]:
    rows = read_json(data_dir / "warehouse" / "qa_events.json")
    return [
        QaEvent(
            lot_id=row["lot_id"],
            ts=parse_dt(row["ts"]),
            type=row["type"],
            reason=row.get("reason", ""),
            seq=int(row.get("seq", 0)),
            qty_mg=int(row.get("qty_mg", 0)),
        )
        for row in rows
    ]


def load_destinations(data_dir: Path) -> dict[str, Destination]:
    rows = read_json(data_dir / "compliance" / "destinations.json")
    return {
        row["dest_id"]: Destination(
            dest_id=row["dest_id"],
            name=row.get("name", row["dest_id"]),
            transit_days=int(row["transit_days"]),
            min_remaining_days=int(row["min_remaining_days"]),
            temp_class=row["temp_class"],
        )
        for row in rows
    }


def load_substitutions(data_dir: Path) -> dict[str, list[str]]:
    rows = read_json(data_dir / "compliance" / "substitutions.json")
    table: dict[str, list[str]] = {}
    for row in rows:
        table[row["warehouse_sku"]] = list(row["accepted_by_customer_skus"])
    return table


def load_orders(data_dir: Path) -> list[Order]:
    rows = read_json(data_dir / "oms" / "orders.json")
    orders = [
        Order(
            order_id=row["order_id"],
            dest_id=row["dest_id"],
            sku=row["sku"],
            qty_mg=int(row["qty_mg"]),
            fill_policy=row["fill_policy"],
        )
        for row in rows
    ]
    return sorted(orders, key=lambda item: item.order_id)


def load_reservations(data_dir: Path) -> list[Reservation]:
    path = data_dir / "oms" / "reservations.json"
    if not path.exists():
        return []
    rows = read_json(path)
    return [
        Reservation(
            order_id=row["order_id"],
            lot_id=row["lot_id"],
            qty_mg=int(row["qty_mg"]),
            reserved_at=parse_dt(row["reserved_at"]),
        )
        for row in rows
    ]
