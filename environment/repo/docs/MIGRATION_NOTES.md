# 2023 picker rewrite (historical)

Warehouse picked FIFO by `received_at` so older pallets moved first. That cut
picker travel time about 8%.

QA status lives on the lot card. We stopped reading the event log during pick
because the snapshot job was "good enough" and the log was "for auditors".

Shelf life: if a lot has 14 days at ship, ship it. International bonded floors
were supposed to land in a later compliance service. Not wired here.

Substitution file was sketched as "customer SKU -> warehouse SKUs we may pick".
Confirm with master data before trusting that orientation.

Weight: persist whatever the handheld shows (kg, 3 decimals).
