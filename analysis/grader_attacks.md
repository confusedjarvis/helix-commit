# Grader attacks

Red-team of the Helix Commit verifier. Each defense below is implemented in `tests/verifier/` and exercised by the unittest suite or `./tools/validate.sh`.

## Attack 1 — Hardcode the workplace cut

**Move.** Run the starter once, then change `pipeline.py` to dump a constant `allocation_result.json` copied from `/app/data`.

**Why it looks good.** The workplace extract is visible. In-repo smoke tests only check that four order IDs appear.

**Defense.** The grader copies candidate `src/` and injects one hidden extract at a time (`HX-DXB-01`, `QA-HELD`, `BRAND-1`, `CW-1`, …). Those IDs do not exist in `/app/data`. The workplace extract is scored as “must also obey policy,” never as the sole golden file. `/app/var/run` is never read.

## Attack 2 — Edit agent-tree tests

**Move.** Edit `/app/tests/test_smoke.py` to `assert True`, or delete it.

**Why it looks good.** Agents often assume repo tests are the grade.

**Defense.** Reward is `python3 -m unittest test_outputs` in the verifier image. Agent-tree tests are not collected. Workplace CLI regression is re-implemented independently in the verifier and executed as an unprivileged child.

## Attack 3 — Partial FEFO / QA / MRL / substitution / weight fix

**Move.** Switch FIFO to FEFO but keep lot-card QA, or keep FIFO and add a 14-day ship-date check, or honor OMS reservations without revalidation.

**Why it looks good.** Domestic Chicago lines start to look reasonable. Several identities still pass.

**Defense.** One hidden suite per mechanism:

| Suite | Rejects |
|---|---|
| `suite_fefo_export` | Receive-date FIFO and the legacy ship-date 14-day floor; the held-out export requires destination-specific arrival MRL |
| `suite_quarantine_reserve` | Snapshot `qa_status` + reserved-lot override |
| `suite_substitution` | Inverted substitution map / exact SKU only |
| `suite_catchweight` | kg-to-3-decimals ledger |
| `suite_ship_complete` | Silent partial on `ship_complete` |
| `suite_temp_class` | “any stock with the SKU” |
| `suite_partial_backorder` | Wrong leftover milligrams |
| `suite_retain_hold` | Last-event `release` restores retain `hold_qty`, or `hold_qty` treated as whole-lot quarantine |

`./tools/validate.sh` also overlays FEFO-only, QA-log-only, and arrival-MRL-only and requires each to fail.

## Attack 4 — Always-success / fake output

**Move.** Mark every order `committed` with empty lines, or copy input quantities into one fake lot.

**Defense.** Inventory identity (`remaining + committed = original`) and per-suite exact line matches. Empty success fails Dubai (must ship `HID-NEW` 2000000) and catch-weight (must drain `CW-1` to 0).

## Attack 5 — Read or import hidden oracle or fixtures

**Move.** During verifier execution, open `/tests/verifier/oracle.py`, import `oracle`, or list `/tests/verifier/fixtures`.

**Defense.**

- Verifier tree is root-only (`0700` directories, `0600` files).
- Candidate runs as uid/gid `10001` after group drop and no-new-privileges.
- Child `PYTHONPATH` is only the copied `src/`.
- Only the current fixture is copied into the candidate work tree.
- Self-tests fail if the low-privilege child can read `oracle.py` or list the fixture corpus.

The agent image also omits the verifier tree; that alone is not the defense during grading.

## Attack 6 — Modify the verifier

**Move.** Append to `oracle.py` or rewrite a hidden fixture from the child.

**Defense.** The candidate uid cannot write `/tests/verifier`. A self-test attempts an append and requires `PermissionError`, then re-reads the oracle bytes.

## Attack 7 — Hang or fork descendants

**Move.** Sleep forever, or `fork` a sleeper and exit the parent.

**Defense.** Each candidate execution has `CANDIDATE_TIMEOUT_SEC` (20s). The child is started in its own session. On timeout the grader sends `SIGKILL` to the process group and fails deterministically. A self-test uses a 1s timeout and a forking sleeper.

## Attack 8 — Rely on network or extra packages

**Move.** Call PyPI, or assume `pytest` must be installed at grade time, or phone home for gold answers.

**Defense.** The verifier image installs nothing from the network. Tests are stdlib `unittest`. `./tools/validate.sh` grades with `--network none`.

## Attack 9 — Edit the policy document

**Move.** Change `/app/docs/ALLOCATION_POLICY.md` so FIFO and lot-card QA become legal, then leave the code.

**Defense.** The independent oracle implements the original policy, not the file the agent can edit.

## Residual risk

A fully correct independent reimplementation of the policy will pass. That is intended: the grade is behavioral. Two experts who follow `ALLOCATION_POLICY.md` get the same milligram vectors.
