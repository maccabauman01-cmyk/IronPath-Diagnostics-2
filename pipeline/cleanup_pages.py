#!/usr/bin/env python3
"""Remove page snapshots and table images — not needed."""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_DIR, MACHINES


def main():
    for machine_id in MACHINES:
        assets = DATA_DIR / machine_id / "assets"
        for folder in ["pages", "tables"]:
            path = assets / folder
            if path.exists():
                count = len(list(path.glob("*.png")))
                shutil.rmtree(path)
                print(f"Removed {count} files from {machine_id}/assets/{folder}/")
        for f in ["page_index.json", "table_index.json"]:
            p = assets / f
            if p.exists():
                p.unlink()


if __name__ == "__main__":
    main()
