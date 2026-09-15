from __future__ import annotations

import json
import os
import stat
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from oracle import expected_from_data_dir
from runner import (
    CANDIDATE_TIMEOUT_SEC,
    CANDIDATE_UID,
    CANDIDATE_GID,
    _candidate_env,
    prepare_work,
    repo_root,
    run_agent_on_fixture,
    run_candidate_argv,
)

COMMIT = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SUITES = [
    "suite_fefo_export",
    "suite_quarantine_reserve",
    "suite_substitution",
    "suite_catchweight",
    "suite_ship_complete",
    "suite_temp_class",
    "suite_partial_backorder",
    "suite_retain_hold",
]
WORKPLACE_ORDERS = {"SO-7702", "SO-7703", "SO-8841", "SO-9100"}
WORKPLACE_LOTS = {"LOT-2214", "LOT-3301", "LOT-1188", "LOT-4402", "LOT-5509", "LOT-6600"}


def _in_verifier_image() -> bool:
    return os.name == "posix" and Path("/tests/verifier/oracle.py").is_file()


def _norm_orders(payload: dict) -> dict:
    orders = {}
    for row in payload["orders"]:
        lines = sorted(row["lines"], key=lambda line: (line["lot_id"], line["sku"], line["qty_mg"]))
        orders[row["order_id"]] = {
            "status": row["status"],
            "backorder_mg": int(row["backorder_mg"]),
            "lines": [(line["lot_id"], line["sku"], int(line["qty_mg"])) for line in lines],
        }
    return orders


def _inv(payload: dict) -> dict[str, int]:
    return {row["lot_id"]: int(row["remaining_mg"]) for row in payload["lots"]}


def _compare(fixture: Path) -> tuple[dict, dict, dict, dict]:
    got_alloc, got_inv = run_agent_on_fixture(fixture)
    exp = expected_from_data_dir(fixture, COMMIT)
    return got_alloc, got_inv, exp, exp["inventory"]


def _assert_valid_cut(test: unittest.TestCase, alloc: dict, inventory: dict) -> None:
    test.assertIn("orders", alloc)
    test.assertIsInstance(alloc["orders"], list)
    test.assertIn("commit_at", alloc)
    test.assertIn("lots", inventory)
    test.assertIsInstance(inventory["lots"], list)
    for row in alloc["orders"]:
        test.assertIn("order_id", row)
        test.assertIn("status", row)
        test.assertIn("backorder_mg", row)
        test.assertIn("lines", row)
        test.assertIsInstance(row["lines"], list)
    for row in inventory["lots"]:
        test.assertIn("lot_id", row)
        test.assertIn("remaining_mg", row)


class OracleSelfCheck(unittest.TestCase):
    def test_independent_oracle_fefo_export_known_answer(self) -> None:
        """Oracle self-check: Dubai must take the eligible FEFO lot, not the short-dated pallet."""
        exp = expected_from_data_dir(FIXTURES / "suite_fefo_export", COMMIT)
        order = exp["orders"][0]
        self.assertEqual(order["order_id"], "HX-DXB-01")
        self.assertEqual(order["status"], "committed")
        self.assertEqual(
            order["lines"],
            [{"order_id": "HX-DXB-01", "lot_id": "HID-MID", "sku": "VX-9", "qty_mg": 2000000}],
        )
        used = {line["lot_id"] for line in order["lines"]}
        self.assertNotIn("HID-OLD", used)

    def test_qa_replay_orders_by_ts_seq_only(self) -> None:
        text = (HERE / "oracle.py").read_text(encoding="utf-8")
        self.assertIn("event.ts, event.seq)", text)
        self.assertNotIn("event.ts, event.seq, event.type", text)

    def test_independent_oracle_retain_hold_known_answer(self) -> None:
        """Oracle self-check: later release does not restore hold_qty; remainder still ships."""
        exp = expected_from_data_dir(FIXTURES / "suite_retain_hold", COMMIT)
        by_id = {row["order_id"]: row for row in exp["orders"]}
        first = by_id["HX-RH-01"]
        self.assertEqual(first["status"], "blocked")
        self.assertEqual(first["lines"], [])
        self.assertEqual(first["backorder_mg"], 700000)
        second = by_id["HX-RH-02"]
        self.assertEqual(second["status"], "committed")
        self.assertEqual(
            second["lines"],
            [{"order_id": "HX-RH-02", "lot_id": "RH-B", "sku": "VX-RH-B", "qty_mg": 600000}],
        )
        inv = {row["lot_id"]: row["remaining_mg"] for row in exp["inventory"]["lots"]}
        self.assertEqual(inv["RH-A"], 1000000)
        self.assertEqual(inv["RH-B"], 200000)


class HiddenSuites(unittest.TestCase):
    def test_agent_matches_oracle_on_all_hidden_suites(self) -> None:
        """Behavior, not filename: each held-out warehouse extract must match the policy engine."""
        for name in SUITES:
            fixture = FIXTURES / name
            got_alloc, got_inv, exp, exp_inv = _compare(fixture)
            self.assertEqual(_norm_orders(got_alloc), _norm_orders(exp), name)
            self.assertEqual(_inv(got_inv), _inv(exp_inv), name)

    def test_inventory_identity_holds(self) -> None:
        """Conservation: remaining + committed = original milligrams on every hidden extract."""
        for name in SUITES:
            fixture = FIXTURES / name
            original = {
                row["lot_id"]: int(row["qty_mg"])
                for row in json.loads((fixture / "warehouse" / "lots.json").read_text(encoding="utf-8"))
            }
            got_alloc, got_inv, _, _ = _compare(fixture)
            committed: dict[str, int] = {lot_id: 0 for lot_id in original}
            for order in got_alloc["orders"]:
                for line in order["lines"]:
                    committed[line["lot_id"]] = committed.get(line["lot_id"], 0) + int(line["qty_mg"])
            remaining = _inv(got_inv)
            for lot_id, start in original.items():
                self.assertGreaterEqual(remaining[lot_id], 0, f"{name} negative {lot_id}")
                self.assertEqual(
                    remaining[lot_id] + committed.get(lot_id, 0),
                    start,
                    f"{name} identity {lot_id}",
                )

    def test_quarantined_lot_never_ships(self) -> None:
        """QA hold at T is a hard stop even when OMS reserved the lot and the card says released."""
        got_alloc, got_inv, _, _ = _compare(FIXTURES / "suite_quarantine_reserve")
        shipped = {line["lot_id"] for order in got_alloc["orders"] for line in order["lines"]}
        self.assertNotIn("QA-HELD", shipped)
        self.assertEqual(got_alloc["orders"][0]["lines"][0]["lot_id"], "QA-FREE")
        self.assertEqual(_inv(got_inv)["QA-HELD"], 4000000)

    def test_export_uses_arrival_mrl_not_ship_date_floor(self) -> None:
        """Bonded 90-day floor is measured at arrival. Older short-dated stock is ineligible."""
        got_alloc, got_inv, _, _ = _compare(FIXTURES / "suite_fefo_export")
        lines = got_alloc["orders"][0]["lines"]
        self.assertEqual([line["lot_id"] for line in lines], ["HID-MID"])
        self.assertEqual(_inv(got_inv)["HID-OLD"], 9000000)
        self.assertEqual(_inv(got_inv)["HID-MID"], 7000000)

    def test_substitution_is_warehouse_to_customer(self) -> None:
        """Generic customer SKU may consume branded warehouse lots listed on the branded row."""
        got_alloc, _, _, _ = _compare(FIXTURES / "suite_substitution")
        order = got_alloc["orders"][0]
        self.assertEqual(order["status"], "committed")
        self.assertEqual(order["lines"][0]["lot_id"], "BRAND-1")
        self.assertEqual(order["lines"][0]["qty_mg"], 800000)

    def test_catchweight_leaves_zero_and_exact_sum(self) -> None:
        """Three milligram picks must drain the lot exactly. kg display rounding is not a ledger."""
        got_alloc, got_inv, _, _ = _compare(FIXTURES / "suite_catchweight")
        total = sum(int(line["qty_mg"]) for order in got_alloc["orders"] for line in order["lines"])
        self.assertEqual(total, 1000000)
        self.assertEqual(_inv(got_inv)["CW-1"], 0)
        self.assertTrue(all(order["status"] == "committed" for order in got_alloc["orders"]))

    def test_ship_complete_does_not_partial_or_deduct(self) -> None:
        """Incomplete ship_complete commits no lines and does not touch inventory."""
        got_alloc, got_inv, _, _ = _compare(FIXTURES / "suite_ship_complete")
        order = got_alloc["orders"][0]
        self.assertEqual(order["status"], "blocked")
        self.assertEqual(order["lines"], [])
        self.assertEqual(order["backorder_mg"], 900000)
        self.assertEqual(_inv(got_inv)["SC-SMALL"], 300000)

    def test_temp_class_mismatch_does_not_ship(self) -> None:
        """Frozen lot cannot fill a 2-8C destination even if SKU and quantity match."""
        got_alloc, got_inv, _, _ = _compare(FIXTURES / "suite_temp_class")
        order = got_alloc["orders"][0]
        self.assertEqual(order["lines"], [])
        self.assertEqual(order["status"], "backordered")
        self.assertEqual(_inv(got_inv)["FZ-1"], 2000000)

    def test_release_does_not_restore_retain_hold(self) -> None:
        """Last-event release is a status change. Open hold_qty stays off the floor."""
        got_alloc, got_inv, _, _ = _compare(FIXTURES / "suite_retain_hold")
        by_id = {row["order_id"]: row for row in got_alloc["orders"]}
        self.assertEqual(by_id["HX-RH-01"]["status"], "blocked")
        self.assertEqual(by_id["HX-RH-01"]["lines"], [])
        self.assertEqual(_inv(got_inv)["RH-A"], 1000000)

    def test_open_hold_qty_still_allows_remainder(self) -> None:
        """A retain hold is not a whole-lot quarantine. The unheld remainder may ship."""
        got_alloc, got_inv, _, _ = _compare(FIXTURES / "suite_retain_hold")
        by_id = {row["order_id"]: row for row in got_alloc["orders"]}
        self.assertEqual(by_id["HX-RH-02"]["status"], "committed")
        self.assertEqual(by_id["HX-RH-02"]["lines"][0]["qty_mg"], 600000)
        self.assertEqual(_inv(got_inv)["RH-B"], 200000)

    def test_partial_backorder_quantity(self) -> None:
        """allow_partial ships what is eligible and reports the leftover milligrams."""
        got_alloc, got_inv, _, _ = _compare(FIXTURES / "suite_partial_backorder")
        order = got_alloc["orders"][0]
        self.assertEqual(order["status"], "backordered")
        self.assertEqual(order["backorder_mg"], 600000)
        self.assertEqual(
            order["lines"],
            [{"order_id": "HX-PB-01", "lot_id": "PB-1", "sku": "VX-9", "qty_mg": 400000}],
        )
        self.assertEqual(_inv(got_inv)["PB-1"], 0)

    def test_hidden_suite_isolation_copies_only_current_fixture(self) -> None:
        got_alloc, _, _, _ = _compare(FIXTURES / "suite_temp_class")
        dumped = json.dumps(got_alloc)
        self.assertNotIn("HID-NEW", dumped)
        self.assertNotIn("QA-HELD", dumped)
        self.assertNotIn("BRAND-1", dumped)
        self.assertNotIn("RH-A", dumped)

    def test_visible_workplace_matches_policy_too(self) -> None:
        """The /app extract is a workplace, not a golden answer file. Policy still applies."""
        data = repo_root() / "data"
        got_alloc, got_inv = run_agent_on_fixture(data)
        exp = expected_from_data_dir(data, COMMIT)
        self.assertEqual(_norm_orders(got_alloc), _norm_orders(exp))
        self.assertEqual(_inv(got_inv), _inv(exp["inventory"]))

    def test_repeated_hidden_export_is_deterministic(self) -> None:
        first, _, _, _ = _compare(FIXTURES / "suite_fefo_export")
        second, _, _, _ = _compare(FIXTURES / "suite_fefo_export")
        self.assertEqual(first, second)


class WorkplaceRegression(unittest.TestCase):
    """Independent of /app/tests. Must hold on the starter and the reference."""

    def test_cli_writes_valid_workplace_artifacts(self) -> None:
        alloc, inventory = run_agent_on_fixture(repo_root() / "data")
        _assert_valid_cut(self, alloc, inventory)
        order_ids = {row["order_id"] for row in alloc["orders"]}
        lot_ids = {row["lot_id"] for row in inventory["lots"]}
        self.assertEqual(order_ids, WORKPLACE_ORDERS)
        self.assertEqual(lot_ids, WORKPLACE_LOTS)

    def test_cli_flags_data_out_config_are_honored(self) -> None:
        work = prepare_work(repo_root() / "src", repo_root() / "data")
        try:
            env = _candidate_env(work / "src", work / "home")
            proc = run_candidate_argv(
                [
                    sys.executable,
                    "-m",
                    "helix_alloc",
                    "--data-dir",
                    str(work / "data"),
                    "--out-dir",
                    str(work / "out"),
                    "--config",
                    str(work / "runtime.toml"),
                ],
                cwd=work,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((work / "out" / "allocation_result.json").is_file())
            self.assertTrue((work / "out" / "inventory_state.json").is_file())
            json.loads((work / "out" / "allocation_result.json").read_text(encoding="utf-8"))
            json.loads((work / "out" / "inventory_state.json").read_text(encoding="utf-8"))
        finally:
            import shutil

            shutil.rmtree(work, ignore_errors=True)

    def test_pipeline_run_api_via_child_process(self) -> None:
        work = prepare_work(repo_root() / "src", repo_root() / "data")
        try:
            env = _candidate_env(work / "src", work / "home")
            script = work / "call_pipeline.py"
            script.write_text(
                "from pathlib import Path\n"
                "from helix_alloc.pipeline import run\n"
                "run(Path('data'), Path('out2'), Path('runtime.toml'))\n",
                encoding="utf-8",
            )
            if hasattr(os, "chown"):
                os.chown(script, CANDIDATE_UID, CANDIDATE_GID)
            (work / "out2").mkdir()
            if hasattr(os, "chown"):
                os.chown(work / "out2", CANDIDATE_UID, CANDIDATE_GID)
            proc = run_candidate_argv(
                [sys.executable, str(script)],
                cwd=work,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads((work / "out2" / "allocation_result.json").read_text(encoding="utf-8"))
            self.assertEqual({row["order_id"] for row in payload["orders"]}, WORKPLACE_ORDERS)
        finally:
            import shutil

            shutil.rmtree(work, ignore_errors=True)


class Isolation(unittest.TestCase):
    def test_runner_never_imports_candidate_or_reads_var_run(self) -> None:
        source = (HERE / "runner.py").read_text(encoding="utf-8")
        self.assertNotIn("import helix_alloc", source)
        self.assertNotIn("from helix_alloc", source)
        self.assertNotIn("importlib", source)
        self.assertNotIn("var/run", source)
        self.assertNotIn("var\\run", source)

    def test_privileged_process_does_not_import_helix_alloc(self) -> None:
        self.assertNotIn("helix_alloc", sys.modules)

    @unittest.skipUnless(_in_verifier_image(), "requires verifier image")
    def test_verifier_tree_mode_excludes_other_and_group(self) -> None:
        mode = Path("/tests/verifier").stat().st_mode
        self.assertEqual(mode & 0o077, 0)
        oracle_mode = Path("/tests/verifier/oracle.py").stat().st_mode
        self.assertEqual(oracle_mode & 0o077, 0)
        self.assertTrue(stat.S_ISDIR(mode))

    @unittest.skipUnless(_in_verifier_image(), "requires verifier image")
    def test_candidate_cannot_read_oracle(self) -> None:
        work = prepare_work(repo_root() / "src", repo_root() / "data")
        try:
            env = _candidate_env(work / "src", work / "home")
            script = work / "probe.py"
            script.write_text(
                "from pathlib import Path\n"
                "p = Path('/tests/verifier/oracle.py')\n"
                "try:\n"
                "    text = p.read_text(encoding='utf-8')\n"
                "except Exception as exc:\n"
                "    print(type(exc).__name__)\n"
                "    raise SystemExit(0)\n"
                "print('LEAK')\n"
                "raise SystemExit(2)\n",
                encoding="utf-8",
            )
            if hasattr(os, "chown"):
                os.chown(script, CANDIDATE_UID, CANDIDATE_GID)
            proc = run_candidate_argv([sys.executable, str(script)], cwd=work, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("LEAK", proc.stdout)
            self.assertIn("PermissionError", proc.stdout + proc.stderr)
        finally:
            import shutil

            shutil.rmtree(work, ignore_errors=True)

    @unittest.skipUnless(_in_verifier_image(), "requires verifier image")
    def test_candidate_cannot_read_hidden_fixture_corpus(self) -> None:
        work = prepare_work(repo_root() / "src", repo_root() / "data")
        try:
            env = _candidate_env(work / "src", work / "home")
            script = work / "probe_fix.py"
            script.write_text(
                "from pathlib import Path\n"
                "root = Path('/tests/verifier/fixtures')\n"
                "try:\n"
                "    names = list(root.iterdir())\n"
                "except Exception as exc:\n"
                "    print(type(exc).__name__)\n"
                "    raise SystemExit(0)\n"
                "print('LEAK', [p.name for p in names])\n"
                "raise SystemExit(2)\n",
                encoding="utf-8",
            )
            if hasattr(os, "chown"):
                os.chown(script, CANDIDATE_UID, CANDIDATE_GID)
            proc = run_candidate_argv([sys.executable, str(script)], cwd=work, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("LEAK", proc.stdout)
        finally:
            import shutil

            shutil.rmtree(work, ignore_errors=True)

    @unittest.skipUnless(_in_verifier_image(), "requires verifier image")
    def test_candidate_cannot_modify_verifier_files(self) -> None:
        work = prepare_work(repo_root() / "src", repo_root() / "data")
        marker = Path("/tests/verifier/oracle.py").read_bytes()
        try:
            env = _candidate_env(work / "src", work / "home")
            script = work / "probe_write.py"
            script.write_text(
                "from pathlib import Path\n"
                "p = Path('/tests/verifier/oracle.py')\n"
                "try:\n"
                "    with p.open('a', encoding='utf-8') as handle:\n"
                "        handle.write('# hack\\n')\n"
                "    print('WROTE')\n"
                "    raise SystemExit(2)\n"
                "except Exception as exc:\n"
                "    print(type(exc).__name__)\n"
                "    raise SystemExit(0)\n",
                encoding="utf-8",
            )
            if hasattr(os, "chown"):
                os.chown(script, CANDIDATE_UID, CANDIDATE_GID)
            proc = run_candidate_argv([sys.executable, str(script)], cwd=work, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("WROTE", proc.stdout)
            self.assertEqual(Path("/tests/verifier/oracle.py").read_bytes(), marker)
        finally:
            import shutil

            shutil.rmtree(work, ignore_errors=True)

    @unittest.skipUnless(_in_verifier_image(), "requires verifier image")
    def test_candidate_env_excludes_verifier_pythonpath_and_oracle_import(self) -> None:
        work = prepare_work(repo_root() / "src", repo_root() / "data")
        try:
            env = _candidate_env(work / "src", work / "home")
            self.assertNotIn("/tests/verifier", env["PYTHONPATH"])
            script = work / "probe_env.py"
            script.write_text(
                "import os, sys\n"
                "print(os.environ.get('PYTHONPATH', ''))\n"
                "try:\n"
                "    import oracle\n"
                "    print('IMPORTED')\n"
                "    raise SystemExit(2)\n"
                "except ImportError:\n"
                "    print('NOIMPORT')\n"
                "    raise SystemExit(0)\n",
                encoding="utf-8",
            )
            if hasattr(os, "chown"):
                os.chown(script, CANDIDATE_UID, CANDIDATE_GID)
            proc = run_candidate_argv([sys.executable, str(script)], cwd=work, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("NOIMPORT", proc.stdout)
            self.assertNotIn("/tests/verifier", proc.stdout.splitlines()[0])
        finally:
            import shutil

            shutil.rmtree(work, ignore_errors=True)


class TimeoutEnforcement(unittest.TestCase):
    def test_timeout_kills_hanging_process_group(self) -> None:
        work = prepare_work(repo_root() / "src", repo_root() / "data")
        try:
            env = _candidate_env(work / "src", work / "home")
            script = work / "hang.py"
            script.write_text(
                "import os, time\n"
                "if hasattr(os, 'fork'):\n"
                "    child = os.fork()\n"
                "    if child == 0:\n"
                "        time.sleep(1000)\n"
                "time.sleep(1000)\n",
                encoding="utf-8",
            )
            if hasattr(os, "chown"):
                os.chown(script, CANDIDATE_UID, CANDIDATE_GID)
            with self.assertRaises(AssertionError) as ctx:
                run_candidate_argv(
                    [sys.executable, str(script)],
                    cwd=work,
                    env=env,
                    timeout_sec=1,
                )
            message = str(ctx.exception)
            self.assertIn("candidate exceeded 1s", message)
            self.assertIn("process group killed", message)
            self.assertIn("leftover=[]", message)
            self.assertGreaterEqual(CANDIDATE_TIMEOUT_SEC, 10)
        finally:
            import shutil

            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
