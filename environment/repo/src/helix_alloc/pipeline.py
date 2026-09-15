from __future__ import annotations

from pathlib import Path

from helix_alloc.allocation import allocate_order
from helix_alloc.catalog import (
    load_destinations,
    load_lots,
    load_orders,
    load_qa_events,
    load_reservations,
    load_substitutions,
)
from helix_alloc.config import load_runtime
from helix_alloc.io_util import write_json
from helix_alloc.models import RunResult


def run(data_dir: Path, out_dir: Path, config_path: Path) -> RunResult:
    cfg = load_runtime(config_path)
    lots = load_lots(data_dir)
    events = load_qa_events(data_dir)
    destinations = load_destinations(data_dir)
    orders = load_orders(data_dir)
    reservations = load_reservations(data_dir)
    substitutions = load_substitutions(data_dir)
    remaining = {lot.lot_id: lot.qty_mg for lot in lots}

    results = []
    for order in orders:
        dest = destinations[order.dest_id]
        results.append(
            allocate_order(
                order,
                dest,
                lots,
                remaining,
                events,
                reservations,
                substitutions,
                cfg.commit_at,
                cfg.weight_unit,
            )
        )

    run_result = RunResult(commit_at=cfg.commit_at, orders=results, inventory=remaining)
    persist(run_result, out_dir)
    return run_result


def persist(run_result: RunResult, out_dir: Path) -> None:
    payload = {
        "commit_at": run_result.commit_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "orders": [
            {
                "order_id": item.order_id,
                "status": item.status,
                "backorder_mg": item.backorder_mg,
                "reason": item.reason,
                "lines": [
                    {
                        "order_id": line.order_id,
                        "lot_id": line.lot_id,
                        "sku": line.sku,
                        "qty_mg": line.qty_mg,
                    }
                    for line in item.lines
                ],
            }
            for item in run_result.orders
        ],
    }
    write_json(out_dir / "allocation_result.json", payload)
    write_json(
        out_dir / "inventory_state.json",
        {
            "lots": [
                {"lot_id": lot_id, "remaining_mg": remaining}
                for lot_id, remaining in sorted(run_result.inventory.items())
            ]
        },
    )
