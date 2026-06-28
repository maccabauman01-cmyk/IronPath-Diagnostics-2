#!/usr/bin/env python3
"""
Milestone 2 — PDF to JSON knowledge base extraction.

Usage:
  python pipeline/extract.py                    # all machines
  python pipeline/extract.py --machine d11t-dozer # single machine
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_DIR, MACHINES
from pipeline.extractors import EXTRACTORS


def process_machine(machine_id: str) -> dict:
    config = MACHINES[machine_id]
    source_dir = config["source_dir"]
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    extractor = EXTRACTORS[config["manufacturer"]]
    pdfs = sorted(source_dir.rglob("*.pdf"))
    all_records = []
    stats = {"pdfs": 0, "records": 0, "errors": []}

    print(f"\nProcessing {config['name']} ({len(pdfs)} PDFs)...")

    for i, pdf_path in enumerate(pdfs, 1):
        try:
            records = extractor(pdf_path, machine_id, config)
            all_records.extend(records)
            stats["pdfs"] += 1
            if i % 50 == 0 or i == len(pdfs):
                print(f"  [{i}/{len(pdfs)}] PDFs — {len(all_records)} records so far")
        except Exception as e:
            stats["errors"].append({"file": str(pdf_path), "error": str(e)})
            print(f"  ERROR: {pdf_path.name}: {e}")

    stats["records"] = len(all_records)

    out_dir = DATA_DIR / machine_id
    out_dir.mkdir(parents=True, exist_ok=True)

    records_path = out_dir / "records.json"
    with open(records_path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in all_records], f, ensure_ascii=False, indent=2)

    manifest = {
        "machine_id": machine_id,
        "machine_name": config["name"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "manual_types": list(config["manual_type_map"].values()),
        "record_count": len(all_records),
        "records_file": "records.json",
    }
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Done: {stats['records']} records → {records_path}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Extract manual PDFs to JSON knowledge base")
    parser.add_argument(
        "--machine",
        choices=list(MACHINES.keys()),
        help="Process a single machine (default: all)",
    )
    args = parser.parse_args()

    machine_ids = [args.machine] if args.machine else list(MACHINES.keys())
    summaries = []

    for mid in machine_ids:
        summaries.append(process_machine(mid))

    summary_path = DATA_DIR / "extraction_summary.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)

    print(f"\nExtraction complete. Summary: {summary_path}")


if __name__ == "__main__":
    main()
