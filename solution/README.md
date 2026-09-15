# Reference solution

Overlay these files onto `environment/repo/src/helix_alloc/`:

- `allocation.py` — FEFO among lots eligible at commit; ignore OMS reservations
- `warehouse.py` — QA event-log replay at `T` (status plus open `hold_qty`)
- `compliance.py` — destination remaining shelf life measured at arrival
- `substitution.py` — warehouse SKU → customer SKUs
- `weights.py` — integer milligram deduction

The verifier does not import this tree. It re-implements the same policy in `tests/verifier/oracle.py`.
