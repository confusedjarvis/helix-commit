# QA event codes (warehouse logger)

Effective 2025-06-01. Amends allocation policy § Eligibility item 4: last-row
type is not the only QA signal.

Replay only events with `ts <= T`, in `(ts, seq)` order.

| type | qty_mg | Effect at commit |
|---|---|---|
| `quarantine` | ignored | Lot status becomes hold. Allocatable = 0. |
| `release` | ignored | Lot status becomes not-hold. Does **not** clear open `hold_qty`. |
| `hold_qty` | required | Add this many milligrams to open hold. Still on the book. |
| `release_qty` | required | Subtract this many milligrams from open hold (floor 0). |

Open hold is a running total across the replay, not “whatever the last row was”.
A lot with status released and open hold 400000 mg has 400000 mg that must not
appear on a commit line.
