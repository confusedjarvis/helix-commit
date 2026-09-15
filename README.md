# Helix Commit

Warehouse lot-allocation service and a Dockerized grade harness. An agent (or engineer) inherits a running codebase, repairs commit-time policy, and is scored on held-out extracts rather than on a single golden JSON file.

## What it measures

The work is **commit-time allocation** for a regulated cold-chain warehouse: compose four file-backed services so the cut matches written policy.

| Surface | Contract |
|---|---|
| Warehouse QA | Event-log replay at frozen time `T`, ordered by `(ts, seq)`, not the cached `qa_status` on the lot card. Hold *status* is last `quarantine`/`release`. Allocatable milligrams subtract open `hold_qty`. A later `release` does not put retain-sample milligrams back on the floor. |
| Compliance | Remaining shelf life versus each destination floor, measured at arrival (`UTC date of T + transit_days`) using the destination `min_remaining_days`. The legacy 14-day ship-date shortcut is invalid. |
| Master data | Substitution table keyed by warehouse SKU → customer SKUs that accept it |
| Ledger | Integer milligrams; kilogram handheld rounding is display-only |

Selection among eligible lots is FEFO (earliest expiry, then `lot_id`). Soft OMS reservations are hints, not ship authority. `ship_complete` is atomic.

A FIFO picker, a 14-day ship-date rule, a lot-card QA flag, or a last-event-only QA replay still writes a commit file and still passes `/app/tests/test_smoke.py`. It fails bonded export, quarantine-after-reserve, retain-sample `hold_qty`, one-way substitution, and milligram conservation.

## Determinism

There is no wall clock, no network, and no thread schedule in the grade path.

- Commit time is a frozen ISO timestamp (`2026-03-15T12:00:00Z` on the workplace extract).
- QA events, lots, destinations, substitutions, orders, and reservations are static JSON.
- Order walk is `order_id` ascending.
- FEFO tie-break is `lot_id` ascending.
- QA replay order is `(ts, seq)`.
- Quantities are integers.

The agent image is `python:3.12.11-slim-bookworm` pinned by digest, non-root uid 1000, `PYTHONPATH=/app/src`. The verifier image uses the same base digest and the Python standard library only.

## Verifier

The grader does not read `/app/var/run` from the workplace run and does not grep the agent tree for policy tokens.

The verifier process stays privileged. Candidate code is never imported into that process. For each scored extract it copies candidate `src/` plus the current fixture, runs `python3 -m helix_alloc` as uid/gid `10001`, sanitizes the child environment, and enforces a per-run timeout.

`/tests/verifier` is root-only. The independent policy engine is `tests/verifier/oracle.py`.

See `analysis/grader_attacks.md` for attack surface and mitigations.

## Layout

```
helix-commit/
├── task/instruction.md
├── task/task.yaml
├── environment/Dockerfile
├── environment/repo/
├── solution/reference_solution/
├── tests/verifier/
├── analysis/grader_attacks.md
├── analysis/model_runs.md
└── README.md
```

## Local grade

```bash
./tools/validate.sh
```

Expected: reference overlays pass, starter and partial mutations fail, agent image leak check passes.

Windows convenience (same images):

```powershell
powershell -File tools/validate.ps1
```

Build a zip **outside** this directory:

```bash
python3 tools/package.py
```

## Model runs

`analysis/model_runs.md` records coding-agent trials on this environment. Mutation-battery results are separate from those scores.
