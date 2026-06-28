#!/usr/bin/env python3
"""
Enrich records: illustration images + structured tables (100% target).

Usage:
  python pipeline/enrich_records.py
  python pipeline/enrich_records.py --machine d11t-dozer
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_DIR, MACHINES
from pipeline.parsers import parse_hitachi_fault_codes
from pipeline.table_parser import extract_tables_pdfplumber, parse_all_tables_from_text


def enrich_machine(machine_id: str) -> dict:
    config = MACHINES[machine_id]
    source_dir = config["source_dir"]
    data_dir = DATA_DIR / machine_id
    records = json.loads((data_dir / "records.json").read_text(encoding="utf-8"))

    ill_index: dict[str, str] = {}
    ill_path = data_dir / "assets" / "illustration_index.json"
    if ill_path.exists():
        ill_index = json.loads(ill_path.read_text())

    hitachi_page_index: dict[str, str] = {}
    hp_path = data_dir / "assets" / "hitachi_page_index.json"
    if hp_path.exists():
        hitachi_page_index = json.loads(hp_path.read_text())

    ill_linked = 0
    figures_linked = 0
    tables_parsed = 0
    tables_pdf_fallback = 0
    table_rows_total = 0
    fault_codes_parsed = 0

    for r in records:
        sf = r["source_file"]

        # Caterpillar illustration IDs → image path
        for ill in r.get("illustrations", []):
            path = ill_index.get(ill["id"])
            ill["image_path"] = path
            if path:
                ill_linked += 1

        # Hitachi: attach figures from pages in this record (cap to avoid icon-grid overload)
        if config["manufacturer"] == "hitachi":
            figures = []
            for p in range(r["page_start"], r["page_end"] + 1):
                for key, path in hitachi_page_index.items():
                    if key.startswith(f"{sf}:{p}:"):
                        figures.append({"page": p, "image_path": path, "key": key})
                        figures_linked += 1
            if figures:
                # Prefer fewer, larger schematic images over dense icon grids
                figures.sort(key=lambda f: (f["page"], f["image_path"]))
                if len(figures) > 8:
                    figures = figures[:8]
                r["figures"] = figures

        # Parse tables from text
        parsed_tables = parse_all_tables_from_text(r.get("body_text", ""))

        # PDFplumber fallback if Table N in text but no rows yet
        if re.search(r"\bTable\s+\d+\b", r.get("body_text", "")) and not parsed_tables:
            pdf_path = source_dir / sf
            if pdf_path.exists():
                for p in range(r["page_start"], r["page_end"] + 1):
                    pdf_tables = extract_tables_pdfplumber(pdf_path, p)
                    if pdf_tables:
                        parsed_tables.extend(pdf_tables)
                        tables_pdf_fallback += len(pdf_tables)
                        break

        # Also try pdfplumber on next page (tables split across pages)
        if re.search(r"\bTable\s+\d+\b", r.get("body_text", "")) and not parsed_tables:
            pdf_path = source_dir / sf
            next_page = r["page_end"] + 1
            if pdf_path.exists():
                pdf_tables = extract_tables_pdfplumber(pdf_path, next_page)
                if pdf_tables:
                    parsed_tables.extend(pdf_tables)
                    tables_pdf_fallback += len(pdf_tables)

        if parsed_tables:
            enriched = []
            for pt in parsed_tables:
                enriched.append({
                    "table_id": pt["table_id"],
                    "title": pt.get("title", ""),
                    "page": r["page_start"],
                    "type": pt["type"],
                    "columns": pt["columns"],
                    "rows": pt["rows"],
                })
            r["tables"] = enriched
            tables_parsed += len(enriched)
            table_rows_total += sum(len(t["rows"]) for t in enriched)
        elif r.get("tables"):
            for tbl in r["tables"]:
                tbl.pop("image_path", None)

        r.pop("page_image_path", None)

        if r.get("manual_type") == "fault-codes":
            codes = parse_hitachi_fault_codes(r["body_text"])
            if codes:
                r["fault_codes"] = codes
                fault_codes_parsed += len(codes)

    (data_dir / "records.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Coverage stats
    ill_refs = sum(len(r.get("illustrations", [])) for r in records)
    ill_missing = sum(1 for r in records for i in r.get("illustrations", []) if not i.get("image_path"))
    table_in_text = sum(1 for r in records if re.search(r"\bTable\s+\d+\b", r.get("body_text", "")))
    table_no_rows = sum(
        1 for r in records
        if re.search(r"\bTable\s+\d+\b", r.get("body_text", ""))
        and not any(t.get("rows") for t in r.get("tables", []))
    )

    stats = {
        "machine_id": machine_id,
        "records": len(records),
        "illustration_images_linked": ill_linked,
        "illustration_refs": ill_refs,
        "illustration_missing": ill_missing,
        "hitachi_figures_linked": figures_linked,
        "tables_with_structured_data": tables_parsed,
        "tables_pdfplumber_fallback": tables_pdf_fallback,
        "table_rows_total": table_rows_total,
        "records_with_table_label": table_in_text,
        "table_label_still_missing": table_no_rows,
        "fault_codes_parsed": fault_codes_parsed,
    }
    print(f"  {stats}")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", choices=list(MACHINES.keys()))
    args = parser.parse_args()
    ids = [args.machine] if args.machine else list(MACHINES.keys())
    stats = [enrich_machine(mid) for mid in ids]
    (DATA_DIR / "enrichment_summary.json").write_text(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
