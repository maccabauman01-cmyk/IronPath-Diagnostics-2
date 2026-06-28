#!/usr/bin/env python3
"""
Build WatermelonDB-compatible seed bundles for mobile apps.

Output per machine:
  data/{machine}/watermelon/
    manifest.json       - bundle metadata + asset list
    machines.json       - machine entry
    manual_records.json - slim records for DB import
    illustrations.json  - flat illustration index
    tables.json         - flat table index
    pages.json          - page image index

Usage:
  python pipeline/build_watermelon_seed.py
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_DIR, MACHINES


def illustration_entries(machine_id: str, r: dict) -> list[dict]:
    """Build flat illustration rows from Caterpillar refs or Hitachi page figures."""
    sf = r["source_file"]
    entries: list[dict] = []

    for ill in r.get("illustrations", []):
        if ill.get("image_path"):
            entries.append({
                "id": ill["id"],
                "record_id": r["id"],
                "label": ill.get("label", ""),
                "page": ill["page"],
                "source_file": sf,
                "image_path": ill["image_path"],
                "machine": machine_id,
            })

    for fig in r.get("figures", []):
        if not fig.get("image_path"):
            continue
        key = fig.get("key", "")
        ill_id = key.split(":")[-1] if key else Path(fig["image_path"]).stem
        entries.append({
            "id": f"{r['id']}_{ill_id}",
            "record_id": r["id"],
            "label": fig.get("label", f"Figure p{fig.get('page', '')}"),
            "page": fig.get("page", r["page_start"]),
            "source_file": sf,
            "image_path": fig["image_path"],
            "machine": machine_id,
        })

    return entries


def _file_hash(data_dir: Path, image_path: str) -> str | None:
    path = data_dir / image_path
    if not path.is_file():
        return None
    return hashlib.md5(path.read_bytes()).hexdigest()


def dedupe_illustrations_by_content(
    entries: list[dict],
    data_dir: Path,
) -> list[dict]:
    """Drop duplicate images per manual record (same bytes, different filenames)."""
    by_record: dict[str, list[dict]] = {}
    for entry in entries:
        by_record.setdefault(entry["record_id"], []).append(entry)

    deduped: list[dict] = []
    for record_id in sorted(by_record.keys()):
        seen_hashes: set[str] = set()
        for entry in by_record[record_id]:
            content_hash = _file_hash(data_dir, entry["image_path"])
            row = {**entry, "content_hash": content_hash}
            if content_hash and content_hash in seen_hashes:
                continue
            if content_hash:
                seen_hashes.add(content_hash)
            deduped.append(row)

    return deduped


def slim_record(r: dict) -> dict:
    return {
        "id": r["id"],
        "machine": r["machine"],
        "manual_type": r["manual_type"],
        "system": r["system"],
        "source_file": r["source_file"],
        "page_start": r["page_start"],
        "page_end": r["page_end"],
        "smcs": r.get("smcs", []),
        "senr_ref": r.get("senr_ref", ""),
        "uenr_ref": r.get("uenr_ref", ""),
        "title": r.get("title", ""),
        "body_text": r.get("body_text", ""),
        "content_type": r.get("content_type", ""),
        "has_troubleshooting_table": r.get("has_troubleshooting_table", False),
        "page_image_path": None,
        "fault_codes": r.get("fault_codes", []),
    }


def build_machine(machine_id: str) -> dict:
    config = MACHINES[machine_id]
    data_dir = DATA_DIR / machine_id
    records = json.loads((data_dir / "records.json").read_text(encoding="utf-8"))

    out_dir = data_dir / "watermelon"
    out_dir.mkdir(parents=True, exist_ok=True)

    illustrations: list[dict] = []
    tables: list[dict] = []

    for r in records:
        sf = r["source_file"]
        illustrations.extend(illustration_entries(machine_id, r))
        for tbl in r.get("tables", []):
            if tbl.get("rows"):
                tables.append({
                    "table_id": tbl.get("table_id", ""),
                    "title": tbl.get("title", ""),
                    "record_id": r["id"],
                    "page": tbl.get("page", r["page_start"]),
                    "source_file": sf,
                    "type": tbl.get("type", ""),
                    "columns": tbl.get("columns", []),
                    "rows": tbl.get("rows", []),
                    "machine": machine_id,
                })

    illustrations = [
        entry for entry in illustrations
        if _file_hash(data_dir, entry["image_path"]) is not None
    ]

    illustrations = dedupe_illustrations_by_content(illustrations, data_dir)

    machine_entry = [{
        "id": machine_id,
        "name": config["name"],
        "record_count": len(records),
        "illustration_count": len(illustrations),
        "table_count": len(tables),
    }]

    (out_dir / "machines.json").write_text(
        json.dumps(machine_entry, indent=2), encoding="utf-8"
    )
    (out_dir / "manual_records.json").write_text(
        json.dumps([slim_record(r) for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "illustrations.json").write_text(
        json.dumps(illustrations, indent=2), encoding="utf-8"
    )
    (out_dir / "tables.json").write_text(
        json.dumps(tables, indent=2), encoding="utf-8"
    )

    assets_ill = sorted((data_dir / "assets" / "illustrations").glob("*.png")) if (data_dir / "assets" / "illustrations").exists() else []
    asset_files = [str(p.relative_to(data_dir)) for p in assets_ill]

    manifest = {
        "machine_id": machine_id,
        "machine_name": config["name"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
        "collections": {
            "machines": "machines.json",
            "manual_records": "manual_records.json",
            "illustrations": "illustrations.json",
            "tables": "tables.json",
        },
        "counts": {
            "records": len(records),
            "illustrations": len(illustrations),
            "tables": len(tables),
            "asset_files": len(asset_files),
        },
        "assets": asset_files,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"  {machine_id}: {manifest['counts']}")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", choices=list(MACHINES.keys()))
    args = parser.parse_args()

    ids = [args.machine] if args.machine else list(MACHINES.keys())
    manifests = []
    for mid in ids:
        manifests.append(build_machine(mid))

    summary = DATA_DIR / "watermelon_summary.json"
    summary.write_text(json.dumps(manifests, indent=2), encoding="utf-8")
    print(f"\nWatermelonDB seed summary: {summary}")


if __name__ == "__main__":
    main()
