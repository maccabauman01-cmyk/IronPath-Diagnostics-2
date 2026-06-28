#!/usr/bin/env python3
"""Run full extraction pipeline targeting 100% images + tables."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    py = sys.executable
    run([py, "pipeline/extract_assets.py", "--force"])
    run([py, "pipeline/enrich_records.py"])
    run([py, "pipeline/build_watermelon_seed.py"])
    run([py, "pipeline/build_index.py"])
    print("\n=== Full extraction complete ===")


if __name__ == "__main__":
    main()
