"""Privileged grader helpers. Never import candidate modules here."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
CANDIDATE_TIMEOUT_SEC = 20
VERIFIER_TREE = Path("/tests/verifier")
DEFAULT_COMMIT = "2026-03-15T12:00:00Z"


def repo_root() -> Path:
    return Path(os.environ.get("HELIX_REPO", "/app")).resolve()


def verifier_root() -> Path:
    return Path(__file__).resolve().parent


def _prctl_no_new_privs() -> None:
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        pr_set_no_new_privs = 38
        libc.prctl(pr_set_no_new_privs, 1, 0, 0, 0)
    except (OSError, AttributeError):
        return


def _preexec_candidate() -> None:
    os.setsid()
    if not hasattr(os, "setuid") or os.geteuid() != 0:
        return
    _prctl_no_new_privs()
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)


def _chown_tree(path: Path) -> None:
    if not hasattr(os, "chown"):
        return
    for root, dirs, files in os.walk(path):
        os.chown(root, CANDIDATE_UID, CANDIDATE_GID)
        for name in dirs + files:
            os.chown(os.path.join(root, name), CANDIDATE_UID, CANDIDATE_GID)


def _candidate_env(src: Path, home: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "PYTHONPATH": str(src),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "TZ": "UTC",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def _kill_process_group(proc: subprocess.Popen[str]) -> None:
    if proc.pid is None:
        return
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
    else:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def pids_in_group(pgid: int) -> list[int]:
    found: list[int] = []
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return found
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        stat_path = entry / "stat"
        try:
            text = stat_path.read_text(encoding="utf-8")
            rparen = text.rfind(")")
            fields = text[rparen + 2 :].split()
            state = fields[0]
            group = int(fields[2])
        except (OSError, IndexError, ValueError):
            continue
        if state == "Z":
            continue
        if group == pgid:
            found.append(int(entry.name))
    return found


def run_candidate_argv(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_sec: int = CANDIDATE_TIMEOUT_SEC,
) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if os.name == "posix":
        kwargs["preexec_fn"] = _preexec_candidate
    proc = subprocess.Popen(argv, **kwargs)
    try:
        stdout, stderr = proc.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        pgid = proc.pid
        _kill_process_group(proc)
        leftover = pids_in_group(pgid) if pgid is not None and os.name == "posix" else []
        raise AssertionError(
            f"candidate exceeded {timeout_sec}s ({CANDIDATE_TIMEOUT_SEC=} default); "
            f"process group killed; leftover={leftover}\n"
            f"argv={argv}\nstdout={exc.stdout!r}\nstderr={exc.stderr!r}"
        ) from exc
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


def prepare_work(src_root: Path, data_src: Path) -> Path:
    work = Path(tempfile.mkdtemp(prefix="helix-cand-"))
    src = work / "src"
    data = work / "data"
    out = work / "out"
    home = work / "home"
    src.mkdir()
    out.mkdir()
    home.mkdir()
    shutil.copytree(src_root, src, dirs_exist_ok=True)
    shutil.copytree(data_src, data)
    commit = DEFAULT_COMMIT
    marker = data_src / "commit_at.txt"
    if marker.exists():
        commit = marker.read_text(encoding="utf-8").strip()
    (work / "runtime.toml").write_text(
        f'commit_at = "{commit}"\nallocation_strategy = "fifo"\nweight_unit = "kg"\n',
        encoding="utf-8",
    )
    _chown_tree(work)
    return work


def run_agent_on_fixture(fixture_dir: Path) -> tuple[dict, dict]:
    repo = repo_root()
    src_root = repo / "src"
    if not src_root.is_dir():
        raise AssertionError(f"candidate src missing: {src_root}")
    work = prepare_work(src_root, fixture_dir)
    try:
        src = work / "src"
        data = work / "data"
        out = work / "out"
        cfg = work / "runtime.toml"
        env = _candidate_env(src, work / "home")
        proc = run_candidate_argv(
            [
                sys.executable,
                "-m",
                "helix_alloc",
                "--data-dir",
                str(data),
                "--out-dir",
                str(out),
                "--config",
                str(cfg),
            ],
            cwd=work,
            env=env,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"agent runner failed ({proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        alloc_path = out / "allocation_result.json"
        inv_path = out / "inventory_state.json"
        if not alloc_path.exists() or not inv_path.exists():
            raise AssertionError("agent did not write allocation_result.json and inventory_state.json")
        return (
            json.loads(alloc_path.read_text(encoding="utf-8")),
            json.loads(inv_path.read_text(encoding="utf-8")),
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
