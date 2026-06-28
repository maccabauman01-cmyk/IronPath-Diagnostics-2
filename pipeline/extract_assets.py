#!/usr/bin/env python3
"""
Extract embedded diagram images from PDFs (illustrations only — not pages, not tables).

Usage:
  python pipeline/extract_assets.py
  python pipeline/extract_assets.py --machine d11t-dozer
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_DIR, MACHINES
from pipeline.illustrations import collect_illustration_refs, extract_all_illustrations


def extract_machine(machine_id: str, force: bool = False) -> dict:
    config = MACHINES[machine_id]
    data_dir = DATA_DIR / machine_id
    records = json.loads((data_dir / "records.json").read_text(encoding="utf-8"))
    ill_dir = data_dir / "assets" / "illustrations"

    index = extract_all_illustrations(
        machine_id,
        config["manufacturer"],
        config["source_dir"],
        records,
        ill_dir,
        force=force,
    )

    if config["manufacturer"] != "hitachi":
        (data_dir / "assets" / "illustration_index.json").write_text(
            json.dumps(index, indent=2), encoding="utf-8"
        )

    refs = collect_illustration_refs(records)
    stats = {
        "machine_id": machine_id,
        "illustration_refs": len(refs) if config["manufacturer"] != "hitachi" else 0,
        "images_extracted": len(list(ill_dir.glob("*.png"))),
    }
    if config["manufacturer"] == "hitachi":
        hp = data_dir / "assets" / "hitachi_page_index.json"
        if hp.exists():
            stats["hitachi_page_images"] = len(json.loads(hp.read_text()))
    print(f"  {config['name']}: {stats}")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", choices=list(MACHINES.keys()))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    ids = [args.machine] if args.machine else list(MACHINES.keys())
    stats = [extract_machine(mid, force=args.force) for mid in ids]
    (DATA_DIR / "asset_extraction_summary.json").write_text(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
