#!/usr/bin/env bash
set -euo pipefail

export HELIX_REPO="${HELIX_REPO:-/app}"
export PYTHONPATH="/tests/verifier"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export TZ=UTC

cd /tests/verifier
exec python3 -m unittest -v test_outputs
