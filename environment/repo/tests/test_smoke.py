import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from helix_alloc.pipeline import run  # noqa: E402


class Smoke(unittest.TestCase):
    def test_runner_writes_both_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            out = Path(raw)
            result = run(ROOT / "data", out, ROOT / "config" / "runtime.toml")
            payload = json.loads((out / "allocation_result.json").read_text(encoding="utf-8"))
            inventory = json.loads((out / "inventory_state.json").read_text(encoding="utf-8"))
            order_ids = {row["order_id"] for row in payload["orders"]}
            self.assertEqual(order_ids, {"SO-7702", "SO-7703", "SO-8841", "SO-9100"})
            self.assertEqual(len(inventory["lots"]), 6)
            self.assertEqual(len(result.orders), 4)

    def test_pipeline_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run(ROOT / "data", Path(raw), ROOT / "config" / "runtime.toml")


if __name__ == "__main__":
    unittest.main()
