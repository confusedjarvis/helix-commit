#!/usr/bin/env python3
"""Summarize structured live-model attempt metadata. Does not invent runs."""

from __future__ import annotations

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


REPORTED_K = (1, 2, 3, 5)


def pass_at_k_exact(n: int, c: int, k: int) -> Fraction | None:
    """Unbiased pass@k: 1 - C(n - c, k) / C(n, k). None if unavailable."""
    if not isinstance(n, int) or not isinstance(c, int) or not isinstance(k, int):
        raise ValueError(f"n, c, k must be int, got {n!r} {c!r} {k!r}")
    if n < 0 or c < 0 or c > n:
        raise ValueError(f"invalid n={n} c={c}")
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if n == 0 or k > n:
        return None
    if c == 0:
        return Fraction(0)
    if c == n or n - c < k:
        return Fraction(1)
    return Fraction(1) - Fraction(math.comb(n - c, k), math.comb(n, k))


def pass_at_k(n: int, c: int, k: int) -> float | None:
    value = pass_at_k_exact(n, c, k)
    if value is None:
        return None
    return float(value)


def load_run(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    if "pass" not in data or "stump" not in data:
        raise ValueError(f"{path} missing pass/stump")
    if not isinstance(data["pass"], bool) or not isinstance(data["stump"], bool):
        raise ValueError(f"{path} pass/stump must be boolean")
    return data


def collect_runs(root: Path) -> list[dict[str, Any]]:
    runs = []
    for path in sorted(root.rglob("run.json")):
        if "testdata" in path.parts and root.name != "model_runs_sample":
            continue
        runs.append(load_run(path))
    return runs


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, list[dict[str, Any]]] = {}
    for row in runs:
        by_model.setdefault(str(row.get("model", "unknown")), []).append(row)
    models = {}
    for name, items in by_model.items():
        items = sorted(items, key=lambda row: int(row.get("attempt", 0)))
        n = len(items)
        c = sum(1 for row in items if row.get("pass") is True)
        stumps = sum(1 for row in items if row.get("stump") is True)
        pass_at: dict[int, float | None] = {}
        for k in range(1, n + 1):
            pass_at[k] = pass_at_k(n, c, k)
        reported = {f"pass@{k}": (pass_at_k(n, c, k) if n else None) for k in REPORTED_K}
        models[name] = {
            "attempts": n,
            "passes": c,
            "failures": n - c,
            "stumps": stumps,
            "empirical_pass_rate": (c / n) if n else None,
            "pass_at": pass_at,
            **reported,
            "stump_percentage": (100.0 * stumps / n) if n else None,
        }
    return {"models": models, "total_attempts": len(runs)}


def _fmt(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.10g}"


def render(summary: dict[str, Any]) -> str:
    header = (
        "model\tattempts\tpasses\tfailures\tstumps\t"
        "empirical_pass_rate\tpass@1\tpass@2\tpass@3\tpass@5\tstump%"
    )
    lines = [header]
    for name, row in sorted(summary["models"].items()):
        lines.append(
            f"{name}\t{row['attempts']}\t{row['passes']}\t{row['failures']}\t"
            f"{row['stumps']}\t{_fmt(row['empirical_pass_rate'])}\t"
            f"{_fmt(row['pass@1'])}\t{_fmt(row['pass@2'])}\t"
            f"{_fmt(row['pass@3'])}\t{_fmt(row['pass@5'])}\t"
            f"{_fmt(row['stump_percentage'])}"
        )
    lines.append(f"total_attempts\t{summary['total_attempts']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "root",
        type=Path,
        help="Directory containing <model>/<attempt>/run.json files",
    )
    args = parser.parse_args()
    if not args.root.is_dir():
        print(f"no run directory: {args.root}", file=sys.stderr)
        return 2
    try:
        runs = collect_runs(args.root)
    except ValueError as exc:
        print(f"malformed run record: {exc}", file=sys.stderr)
        return 2
    if not runs:
        print("NO RUNS FOUND")
        print("No recorded coding-agent attempts are present in this trace directory.")
        return 0
    sys.stdout.write(render(summarize(runs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
