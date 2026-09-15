from __future__ import annotations

import argparse
from pathlib import Path

from helix_alloc.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Helix Commit allocation runner")
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data"))
    parser.add_argument("--out-dir", type=Path, default=Path("/app/var/run"))
    parser.add_argument("--config", type=Path, default=Path("/app/config/runtime.toml"))
    args = parser.parse_args()
    run(args.data_dir, args.out_dir, args.config)


if __name__ == "__main__":
    main()
