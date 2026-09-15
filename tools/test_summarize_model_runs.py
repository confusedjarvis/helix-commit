#!/usr/bin/env python3
"""Stdlib unit tests for summarize_model_runs.py using SYNTHETIC_TOOL_TEST data."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from summarize_model_runs import (
    collect_runs,
    load_run,
    main,
    pass_at_k,
    pass_at_k_exact,
    summarize,
)

SAMPLE = Path(__file__).resolve().parent / "testdata" / "model_runs_sample"
TRACES = Path(__file__).resolve().parent.parent / "analysis" / "traces"


class PassAtKFormula(unittest.TestCase):
    def test_case_a_n5_c2(self) -> None:
        self.assertEqual(pass_at_k_exact(5, 2, 1), Fraction(2, 5))
        self.assertEqual(pass_at_k_exact(5, 2, 2), Fraction(7, 10))
        self.assertEqual(pass_at_k_exact(5, 2, 3), Fraction(9, 10))
        self.assertEqual(pass_at_k_exact(5, 2, 4), Fraction(1))
        self.assertEqual(pass_at_k_exact(5, 2, 5), Fraction(1))
        self.assertAlmostEqual(pass_at_k(5, 2, 1), 0.4)
        self.assertAlmostEqual(pass_at_k(5, 2, 2), 0.7)
        self.assertAlmostEqual(pass_at_k(5, 2, 3), 0.9)
        self.assertAlmostEqual(pass_at_k(5, 2, 4), 1.0)
        self.assertAlmostEqual(pass_at_k(5, 2, 5), 1.0)

    def test_case_b_n5_c0(self) -> None:
        for k in range(1, 6):
            self.assertEqual(pass_at_k_exact(5, 0, k), Fraction(0))
            self.assertEqual(pass_at_k(5, 0, k), 0.0)

    def test_case_c_n5_c5(self) -> None:
        for k in range(1, 6):
            self.assertEqual(pass_at_k_exact(5, 5, k), Fraction(1))
            self.assertEqual(pass_at_k(5, 5, k), 1.0)

    def test_case_d_n1_c1(self) -> None:
        self.assertEqual(pass_at_k_exact(1, 1, 1), Fraction(1))
        self.assertEqual(pass_at_k(1, 1, 1), 1.0)

    def test_case_f_k_greater_than_n(self) -> None:
        self.assertIsNone(pass_at_k_exact(5, 2, 6))
        self.assertIsNone(pass_at_k(2, 1, 3))

    def test_n_zero_unavailable(self) -> None:
        self.assertIsNone(pass_at_k_exact(0, 0, 1))
        self.assertIsNone(pass_at_k(0, 0, 1))

    def test_k_less_than_one_rejected(self) -> None:
        with self.assertRaises(ValueError):
            pass_at_k(5, 2, 0)

    def test_invalid_counts_rejected(self) -> None:
        with self.assertRaises(ValueError):
            pass_at_k(3, 4, 1)


class SummarizeSample(unittest.TestCase):
    def test_sample_is_clearly_synthetic(self) -> None:
        readme = (SAMPLE / "README.txt").read_text(encoding="utf-8")
        self.assertIn("SYNTHETIC_TOOL_TEST", readme)
        self.assertIn("not live", readme.lower())

    def test_counts_use_combinatorial_pass_at_k(self) -> None:
        runs = collect_runs(SAMPLE)
        self.assertEqual(len(runs), 3)
        summary = summarize(runs)
        x = summary["models"]["sample-model-x"]
        y = summary["models"]["sample-model-y"]
        self.assertEqual(x["attempts"], 2)
        self.assertEqual(x["passes"], 1)
        self.assertEqual(x["stumps"], 0)
        self.assertAlmostEqual(x["empirical_pass_rate"], 0.5)
        self.assertAlmostEqual(x["pass@1"], 0.5)
        self.assertAlmostEqual(x["pass@2"], 1.0)
        self.assertIsNone(x["pass@3"])
        self.assertIsNone(x["pass@5"])
        self.assertNotEqual(x.get("pass@2"), x["empirical_pass_rate"])
        self.assertEqual(y["attempts"], 1)
        self.assertEqual(y["passes"], 0)
        self.assertEqual(y["stumps"], 1)
        self.assertEqual(y["pass@1"], 0.0)
        self.assertIsNone(y["pass@2"])
        self.assertEqual(y["stump_percentage"], 100.0)
        self.assertEqual(summary["total_attempts"], 3)


class ZeroRunAndMalformed(unittest.TestCase):
    def test_case_e_no_live_runs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            empty = Path(raw)
            buf = io.StringIO()
            with patch.object(sys, "argv", ["summarize_model_runs.py", str(empty)]):
                with patch.object(sys, "stdout", buf):
                    code = main()
            self.assertEqual(code, 0)
            text = buf.getvalue()
            self.assertIn("NO RUNS FOUND", text)
            self.assertNotIn("0.0", text)
            self.assertNotIn("pass@1", text)

    def test_live_traces_dir_has_no_run_json(self) -> None:
        self.assertEqual(list(TRACES.rglob("run.json")), [])
        buf = io.StringIO()
        with patch.object(sys, "argv", ["summarize_model_runs.py", str(TRACES)]):
            with patch.object(sys, "stdout", buf):
                code = main()
        self.assertEqual(code, 0)
        self.assertIn("NO RUNS FOUND", buf.getvalue())

    def test_malformed_record_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "run.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_run(path)
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_run(path)
            path.write_text(json.dumps({"pass": "yes", "stump": False}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_run(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
