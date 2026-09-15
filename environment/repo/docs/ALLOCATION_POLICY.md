# Helix Commit allocation policy (effective 2024-11-01)

This document is the contract used by QA, bonded-warehouse compliance, and finance.
Nightly screens, leftover feature flags, and warehouse-speed notes do not override it.

## Clock

Commit time `T` is taken from the frozen cut supplied to the runner. Do not use wall
clock. Lot expiry is a calendar date. Arrival date is the UTC date of `T` plus the
destination `transit_days`.

## Eligibility at commit

A lot may be committed to an order only when every check below is true at `T`:

1. Temperature class of the lot equals the destination temperature class.
2. The lot is not expired on the UTC date of `T` (`expiry > T.date()`).
3. Remaining shelf life at **arrival** is at least the destination `min_remaining_days`:
   `(expiry - arrival_date).days >= dest.min_remaining_days`.
4. Quality **status** and quality **quantity** are different. The warehouse QA event
   log is authoritative for both. Replay events for that `lot_id` with `ts <= T`,
   ordered by `(ts, seq)`. The lot card `qa_status` is a cached label and is not
   sufficient for commit.

   Whole-lot `quarantine` / `release` set or clear hold *status*. The lot is on
   hold if, after replay, the last status-changing event is `quarantine`. If there
   is no status event, the lot is not on hold.

   `hold_qty` / `release_qty` change how many milligrams are **allocatable**. Those
   milligrams stay in the building and stay on the book (`remaining_mg` still counts
   them). They are not shippable. A later whole-lot `release` ends quarantine only;
   it does not put retain-sample or damage holds back on the floor. Only
   `release_qty` returns that many milligrams to allocatable. If hold status is
   active, allocatable is zero regardless of `hold_qty`.

   Event codes are listed in `docs/QA_EVENT_CODES.md`.
5. SKU fit: the lot SKU equals the order SKU, **or** the order SKU appears in
   `accepted_by_customer_skus` for that **warehouse** SKU. The substitution table is
   keyed by warehouse SKU. A generic customer SKU may take a branded warehouse lot
   when the branded row lists the generic SKU. The reverse is not implied.

## Soft reservations

A reservation in OMS is a pick hint only. It is not ship authority. If a reserved
lot fails eligibility at `T`, release it and allocate from currently eligible lots.
Do not ship a reserved lot that is on QA hold, short-dated for the destination, or
the wrong temperature class.

## Selection

Among lots that are eligible at `T`, allocate **FEFO**: earliest expiry first,
`lot_id` ascending as the tie-break. Do not use receive-date FIFO for commit.

Walk eligible lots in that order and take `min(remaining, still_needed)` each time.

## Fill policy

- `ship_complete`: if the full order quantity cannot be covered by eligible lots,
  commit nothing for that order. Status `blocked`, `backorder_mg` equals the order
  quantity, no inventory deduction.
- `allow_partial`: commit what eligible lots can cover. Leftover quantity is
  `backorder_mg`. Status `committed` when leftover is 0, otherwise `backordered`.

Orders are processed in `order_id` ascending order. Later orders see remaining
quantities after earlier commits.

## Quantities

All inventory arithmetic is integer milligrams. Do not convert through kilogram
display rounding. After a successful commit:

`sum(remaining_mg) + sum(committed line qty_mg) = sum(original lot qty_mg)`

A lot's remaining quantity must never go negative. A lot that is on QA hold at `T`
must have zero committed milligrams in the run.

## Temperature

Exact class match only. A `-20C` lot cannot fill a `2-8C` destination.
