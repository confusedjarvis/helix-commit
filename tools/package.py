#!/usr/bin/env python3
"""Build a POSIX-separator zip of this repository."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile
from pathlib import Path

ARCHIVE_ROOT = "helix-commit"
EXCLUDE_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    ".mypy_cache",
    "archive",
}
EXCLUDE_REL_PREFIXES = (("analysis", "traces"),)
EXCLUDE_FILE_NAMES = {
    ".DS_Store",
    "helix-commit.zip",
}
EXEC_SUFFIXES = {".sh"}
ZIP_EPOCH = (2026, 1, 1, 0, 0, 0)
REQUIRED_MEMBERS = (
    f"{ARCHIVE_ROOT}/README.md",
    f"{ARCHIVE_ROOT}/task/instruction.md",
    f"{ARCHIVE_ROOT}/task/task.yaml",
    f"{ARCHIVE_ROOT}/environment/Dockerfile",
    f"{ARCHIVE_ROOT}/environment/repo/src/helix_alloc/__main__.py",
    f"{ARCHIVE_ROOT}/solution/reference_solution/src/helix_alloc/allocation.py",
    f"{ARCHIVE_ROOT}/tests/verifier/oracle.py",
    f"{ARCHIVE_ROOT}/tests/verifier/runner.py",
    f"{ARCHIVE_ROOT}/tests/verifier/test_outputs.py",
    f"{ARCHIVE_ROOT}/tests/verifier/Dockerfile",
    f"{ARCHIVE_ROOT}/analysis/grader_attacks.md",
    f"{ARCHIVE_ROOT}/analysis/model_runs.md",
    f"{ARCHIVE_ROOT}/tools/validate.sh",
    f"{ARCHIVE_ROOT}/tools/grade_candidates.sh",
    f"{ARCHIVE_ROOT}/tools/package.py",
    f"{ARCHIVE_ROOT}/tools/summarize_model_runs.py",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def should_skip(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(rel_parts[: len(prefix)] == prefix for prefix in EXCLUDE_REL_PREFIXES):
        return True
    if any(part in EXCLUDE_DIR_NAMES for part in rel_parts):
        return True
    if any(part.startswith(".tmp-validate-") or part.startswith(".tmp-grade-") for part in rel_parts):
        return True
    if path.name in EXCLUDE_FILE_NAMES:
        return True
    if path.suffix in {".pyc", ".pyo"}:
        return True
    return False


def unix_mode(path: Path) -> int:
    if path.suffix in EXEC_SUFFIXES or path.name.endswith(".sh"):
        return 0o100755
    return 0o100644


def build_zip(root: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in EXCLUDE_DIR_NAMES
            and not name.startswith(".tmp-validate-")
            and not name.startswith(".tmp-grade-")
            and not (
                Path(current).resolve() == (root / "analysis").resolve()
                and name == "traces"
            )
        )
        for name in sorted(filenames):
            path = current_path / name
            if should_skip(path, root):
                continue
            files.append(path)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            rel = path.relative_to(root).as_posix()
            arcname = f"{ARCHIVE_ROOT}/{rel}"
            if "\\" in arcname:
                raise RuntimeError(f"backslash in archive name: {arcname}")
            info = zipfile.ZipInfo(arcname)
            info.date_time = ZIP_EPOCH
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = unix_mode(path) << 16
            archive.writestr(info, path.read_bytes())


def validate_zip(dest: Path) -> None:
    with zipfile.ZipFile(dest, "r") as archive:
        names = archive.namelist()
    if not names:
        raise RuntimeError("empty archive")
    for name in names:
        if "\\" in name:
            raise RuntimeError(f"member contains backslash: {name}")
        if name.startswith("/") or name.startswith("\\"):
            raise RuntimeError(f"absolute member: {name}")
        if ".." in Path(name).parts:
            raise RuntimeError(f"traversal member: {name}")
        if "__pycache__" in name or name.endswith(".pyc"):
            raise RuntimeError(f"cache member: {name}")
        if f"{ARCHIVE_ROOT}/analysis/traces/" in name:
            raise RuntimeError(f"traces must not ship: {name}")
    missing = [item for item in REQUIRED_MEMBERS if item not in names]
    if missing:
        raise RuntimeError(f"missing required members: {missing}")
    with zipfile.ZipFile(dest, "r") as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"corrupt member: {bad}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Destination ZIP. Default: ../helix-commit.zip",
    )
    args = parser.parse_args()
    root = repo_root()
    dest = args.output
    if dest is None:
        dest = root.parent / "helix-commit.zip"
    dest = dest.resolve()
    if dest.is_relative_to(root):
        raise SystemExit("output ZIP must live outside the repository root")
    build_zip(root, dest)
    validate_zip(dest)
    print(dest)
    print(f"sha256 {sha256_file(dest)}")
    print(f"members {len(zipfile.ZipFile(dest).namelist())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
