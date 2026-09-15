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
WORKDIR="$ROOT/.tmp-grade-$$"
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

if ! docker image inspect "$VERIFIER_IMAGE" >/dev/null 2>&1; then
  docker build -t "$VERIFIER_IMAGE" -f "$DOCKER_ROOT/tests/verifier/Dockerfile" "$DOCKER_ROOT/tests/verifier"
fi

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

OUT="$ROOT/analysis/candidate_results.txt"
: > "$OUT"

record() {
  local name="$1"
  local tree="$2"
  shift 2
  copy_repo "$tree"
  if [ "$#" -gt 0 ]; then
    overlay_ref "$tree" "$@"
  fi
  set +e
  grade "$tree"
  local code=$?
  set -e
  echo "$name exit=$code" | tee -a "$OUT"
}

record nop "$WORKDIR/nop"
record oracle "$WORKDIR/oracle" allocation.py warehouse.py compliance.py substitution.py weights.py
record fefo_only "$WORKDIR/fefo" allocation.py
record qa_log_only "$WORKDIR/qa" warehouse.py
record arrival_mrl_only "$WORKDIR/mrl" compliance.py

echo "Wrote $OUT"
echo "These are handcrafted candidate/mutation results, not live model runs."
