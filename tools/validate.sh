#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then
  DOCKER_ROOT="$(cygpath -m "$ROOT")"
else
  DOCKER_ROOT="$ROOT"
fi
cd "$ROOT"

AGENT_IMAGE="${AGENT_IMAGE:-helix-commit-agent}"
VERIFIER_IMAGE="${VERIFIER_IMAGE:-helix-commit-verifier}"
WORKDIR="$ROOT/.tmp-validate-$$"
mkdir -p "$WORKDIR"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

docker_path() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m "$1"
  else
    printf '%s\n' "$1"
  fi
}

grade() {
  local tree="$1"
  docker run --rm --network none \
    -e HELIX_REPO=/app \
    -v "$(docker_path "$tree"):/app" \
    "$VERIFIER_IMAGE"
}

copy_repo() {
  local dest="$1"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -a "$ROOT/environment/repo/." "$dest/"
}

overlay_ref() {
  local dest="$1"
  shift
  local file
  for file in "$@"; do
    cp "$ROOT/solution/reference_solution/src/helix_alloc/$file" \
      "$dest/src/helix_alloc/$file"
  done
}

echo "==> build agent image"
docker build -t "$AGENT_IMAGE" -f "$DOCKER_ROOT/environment/Dockerfile" "$DOCKER_ROOT/environment"

echo "==> build verifier image"
docker build -t "$VERIFIER_IMAGE" -f "$DOCKER_ROOT/tests/verifier/Dockerfile" "$DOCKER_ROOT/tests/verifier"

echo "==> agent image must not contain solution/verifier/oracle material"
docker run --rm --network none --user 0 --entrypoint /bin/bash "$AGENT_IMAGE" -lc '
  set -euo pipefail
  if [ -e /solution ] || [ -e /tests/verifier ]; then
    echo "forbidden tree present in agent image" >&2
    exit 1
  fi
  hits="$(find / -xdev \( \
      -name oracle.py -o \
      -name suite_fefo_export -o \
      -name suite_retain_hold -o \
      -name reference_solution -o \
      -path "*/solution/reference_solution/*" \
    \) 2>/dev/null || true)"
  if [ -n "$hits" ]; then
    echo "$hits" >&2
    echo "agent image leak" >&2
    exit 1
  fi
  echo "agent image leak check PASS"
'

echo "==> verifier Dockerfile must not install PyPI packages"
if grep -nE 'pip install|pytest==' "$ROOT/tests/verifier/Dockerfile" "$ROOT/tests/verifier/run.sh"; then
  echo "verifier still depends on network package install" >&2
  exit 1
fi

echo "==> reference / oracle 3/3"
for i in 1 2 3; do
  tree="$WORKDIR/oracle-$i"
  copy_repo "$tree"
  overlay_ref "$tree" allocation.py warehouse.py compliance.py substitution.py weights.py
  grade "$tree"
  echo "oracle run $i PASS"
done

echo "==> starter / NOP 3/3 must FAIL"
for i in 1 2 3; do
  tree="$WORKDIR/nop-$i"
  copy_repo "$tree"
  if grade "$tree"; then
    echo "NOP run $i unexpectedly passed" >&2
    exit 1
  fi
  echo "NOP run $i FAIL as required"
done

echo "==> partial mutations must FAIL"
copy_repo "$WORKDIR/fefo"
overlay_ref "$WORKDIR/fefo" allocation.py
if grade "$WORKDIR/fefo"; then echo "FEFO-only unexpectedly passed" >&2; exit 1; fi
echo "FEFO-only FAIL as required"

copy_repo "$WORKDIR/qa"
overlay_ref "$WORKDIR/qa" warehouse.py
if grade "$WORKDIR/qa"; then echo "QA-log-only unexpectedly passed" >&2; exit 1; fi
echo "QA-log-only FAIL as required"

copy_repo "$WORKDIR/mrl"
overlay_ref "$WORKDIR/mrl" compliance.py
if grade "$WORKDIR/mrl"; then echo "arrival-MRL-only unexpectedly passed" >&2; exit 1; fi
echo "arrival-MRL-only FAIL as required"

echo "validate.sh PASS"
echo "Security, timeout, isolation, and determinism checks are part of the verifier suite above."
echo "Live two-model evaluation is NOT performed by this script."
