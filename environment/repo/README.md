# Helix Commit

Internal allocation service used by warehouse ops to turn a frozen OMS/WMS
extract into a commit cut.

    PYTHONPATH=/app/src python3 -m helix_alloc \
      --data-dir /app/data \
      --out-dir /app/var/run \
      --config /app/config/runtime.toml

Policy: `docs/ALLOCATION_POLICY.md`.
Incident: `docs/INCIDENT.md`.
