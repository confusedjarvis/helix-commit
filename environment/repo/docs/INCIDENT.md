From: ops-oncall@helix-biologistics.example
To: warehouse-eng@helix-biologistics.example
Subject: Dubai short-dated ship + Frankfurt quarantine leak (2026-03-15 cut)

Three tickets landed on the same commit cut. Please repair Helix Commit. Do not
paper over the extract — finance will replay other warehouses against the same
binary.

1. SO-7702 Dubai bonded. Customer QA rejected the lot. Remaining shelf life at
   arrival was under the 90-day bonded floor. The lot card still looked fine on
   the Chicago rule of thumb (two weeks from ship date). Older receive-date stock
   was preferred.

2. SO-8841 Frankfurt. OMS had a soft reserve on LOT-1188. QA quarantined that lot
   after reserve and before commit (logger gap). The shipment still went. The lot
   card still said released because the snapshot job runs at 06:00.

3. SO-9100 generic vial label. We had branded VX-9 that the substitution matrix
   allows for that customer SKU, but commit either missed it or grabbed the wrong
   direction when the generic warehouse lot was short.

4. Cycle count: milligram inventory is drifting after several catch-weight picks
   off one lot. Screens show kg to three decimals. Ledger must stay in mg.

5. Retain-sample leak. QA pulled 200 g off a released lot as `hold_qty`, then a
   later whole-lot `release` (logger catch-up after an earlier quarantine) made
   Helix treat the pallet as fully shippable. Finance almost committed through the
   retain. Status can be released while milligrams are still off the floor.

`docs/MIGRATION_NOTES.md` is from the 2023 picker rewrite. It is not policy.
`config/runtime.toml` still has leftover picker flags. Policy in
`ALLOCATION_POLICY.md` is the contract.

Reproduce with:

    PYTHONPATH=/app/src python3 -m helix_alloc \
      --data-dir /app/data \
      --out-dir /app/var/run \
      --config /app/config/runtime.toml

Outputs: `/app/var/run/allocation_result.json` and `/app/var/run/inventory_state.json`.
