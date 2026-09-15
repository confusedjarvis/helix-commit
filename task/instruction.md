Warehouse engineering needs Helix Commit fixed before finance replays next week's extracts. The service lives at `/app`. It reads a frozen warehouse/OMS/compliance extract and writes a commit cut. The binary will be pointed at other warehouses; do not bake tonight's Chicago numbers into the runner.

The workplace packet under `/app/docs` and `/app/data` is the contract. `/app/docs/ALLOCATION_POLICY.md` is the 2024-11-01 baseline. Later dated QA notes in that folder amend named rules. `/app/docs/INCIDENT.md` is the ticket. `/app/docs/MIGRATION_NOTES.md` is a 2023 picker memo and is not policy. `/app/config/runtime.toml` leftover flags (`allocation_strategy`, `weight_unit`) do not override the packet. Do not edit the policy document to match the current code.

Data on disk is a workplace extract, not a golden answer:

- `/app/data/warehouse/lots.json`
- `/app/data/warehouse/qa_events.json`
- `/app/data/compliance/destinations.json`
- `/app/data/compliance/substitutions.json`
- `/app/data/oms/orders.json`
- `/app/data/oms/reservations.json`

Reproduce with:

`PYTHONPATH=/app/src python3 -m helix_alloc --data-dir /app/data --out-dir /app/var/run --config /app/config/runtime.toml`

The runner must keep that CLI and still emit `/app/var/run/allocation_result.json` plus `/app/var/run/inventory_state.json` when those paths are passed. Scoring re-runs your code against held-out extracts. Preserve behavior that already matches policy. `/app/tests/test_smoke.py` only checks that the runner starts.

You have 3600 seconds.
