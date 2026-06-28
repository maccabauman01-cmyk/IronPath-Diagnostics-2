#!/usr/bin/env python3
"""Validate manual data links: records ↔ illustrations ↔ tables ↔ PNG files."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_DIR, MACHINES


def validate_machine(machine_id: str) -> dict:
    data_dir = DATA_DIR / machine_id
    records = json.loads((data_dir / "records.json").read_text(encoding="utf-8"))
    rec_ids = {r["id"] for r in records}
    rec_by_id = {r["id"]: r for r in records}

    wm = data_dir / "watermelon"
    illustrations = json.loads((wm / "illustrations.json").read_text())
    tables = json.loads((wm / "tables.json").read_text())

    issues: list[str] = []

    orphan_ill = [i for i in illustrations if i["record_id"] not in rec_ids]
    orphan_tbl = [t for t in tables if t["record_id"] not in rec_ids]
    if orphan_ill:
        issues.append(f"{len(orphan_ill)} illustrations with unknown record_id")
    if orphan_tbl:
        issues.append(f"{len(orphan_tbl)} tables with unknown record_id")

    missing_png = []
    for ill in illustrations:
        path = data_dir / ill["image_path"]
        if not path.is_file():
            missing_png.append(ill["image_path"])

    records_without_tables = 0
    multi_section = 0
    for r in records:
        tbls = r.get("tables") or []
        if r.get("has_troubleshooting_table") and not tbls:
            records_without_tables += 1
        if sum(1 for t in tbls if t.get("type") == "procedure_steps") > 1:
            multi_section += 1

    ill_per_rec: dict[str, int] = {}
    for ill in illustrations:
        ill_per_rec[ill["record_id"]] = ill_per_rec.get(ill["record_id"], 0) + 1
    heavy_ill = sum(1 for c in ill_per_rec.values() if c > 8)

    return {
        "machine_id": machine_id,
        "records": len(records),
        "illustrations": len(illustrations),
        "tables": len(tables),
        "orphan_illustrations": len(orphan_ill),
        "orphan_tables": len(orphan_tbl),
        "missing_png": len(missing_png),
        "records_missing_expected_tables": records_without_tables,
        "records_with_split_procedures": multi_section,
        "records_with_many_illustrations": heavy_ill,
        "issues": issues + ([f"{len(missing_png)} illustration PNGs missing on disk"] if missing_png else []),
        "ok": not issues and not missing_png,
    }


def main():
    results = [validate_machine(mid) for mid in MACHINES]
    summary_path = DATA_DIR / "validation_summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    for r in results:
        status = "OK" if r["ok"] else "ISSUES"
        print(
            f"[{status}] {r['machine_id']}: "
            f"{r['records']} records, {r['illustrations']} ill, {r['tables']} tbl, "
            f"split_procedures={r['records_with_split_procedures']}"
        )
        for issue in r["issues"]:
            print(f"       - {issue}")

    print(f"\nWrote {summary_path}")
    if not all(r["ok"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
