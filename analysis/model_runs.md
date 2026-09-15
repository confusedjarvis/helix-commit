# Model Evaluation

## Evaluation protocol

The coding-agent evaluation used two distinct model families under the same task contract and hardened verifier:

- `gpt-5.6-sol-xhigh`
- `claude-opus-5-thinking-high`

Each primary evaluation attempt started from a pristine copy of `environment/repo/`. Agents received the starter repository and `task/instruction.md`. The reference solution, verifier implementation, independent oracle, hidden fixtures, and prior-attempt patches were withheld. Completed attempts were graded with the same hardened verifier under network-disabled conditions.

## Primary quantitative result

The primary aggregate evaluation result is **2 successful attempts out of 5 total attempts**.

| Attempts | Passes | Failures | Empirical pass rate | pass@1 | pass@2 | pass@3 | pass@5 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 2 | 3 | 40% | 0.40 | 0.70 | 0.90 | 1.00 |

For a cohort with `n` independent attempts and `c` successful attempts, the standard estimator is:

`pass@k = 1 - C(n-c,k) / C(n,k)`

For `n=5` and `c=2`, this gives `pass@1=0.40`, `pass@2=0.70`, `pass@3=0.90`, `pass@4=1.00`, and `pass@5=1.00`.

Machine-readable aggregate data is stored in `analysis/model_evaluation_summary.json`.

## Stump analysis

A stump is defined as an attempt that terminates without a substantive implementation attempt. An incorrect but substantive implementation is a normal failure, not a stump.

The primary 5-attempt aggregate records the pass/fail result used for pass@k. A cohort-level stump count is not asserted unless directly supported by the primary evaluation record.

## Qualitative analysis

The main reasoning burden is cross-cutting policy reconciliation rather than a local bug fix. Correct implementations have to coordinate warehouse QA replay, compliance timing, SKU substitution, FEFO lot selection, reservation semantics, atomic `ship_complete` handling, temperature compatibility, and integer-milligram accounting.

Successful approaches consistently addressed these interactions:

1. replay QA events by `(ts, seq)` and distinguish whole-lot quarantine state from quantity-level holds
2. measure destination minimum remaining shelf life at arrival rather than using the legacy ship-date shortcut
3. use FEFO with `lot_id` as the deterministic tie-break
4. treat OMS reservations as hints rather than ship authority
5. apply substitution in the warehouse-SKU to accepted-customer-SKU direction
6. preserve exact ledger arithmetic in integer milligrams

The verifier separately exercises realistic failure modes, including FIFO instead of FEFO, ship-date shelf-life checks, shipping quarantined or quantity-held stock, reversed substitution direction, trusting soft reservations, partial `ship_complete` deductions, temperature mismatches, and conservation errors.

## Mutation battery

The NOP, FEFO-only, QA-only, and arrival-MRL-only candidates are verifier-robustness checks. They are **not** counted as coding-agent model attempts and do not contribute to the model-evaluation metrics above.

## Limitations

The primary cohort contains five attempts, which is still a small evaluation sample.
