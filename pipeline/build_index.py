#!/usr/bin/env python3
"""Build SQLite FTS5 search index from extracted JSON records."""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_DIR, MACHINES


def build_index(machine_id: str) -> dict:
    records_path = DATA_DIR / machine_id / "records.json"
    if not records_path.exists():
        raise FileNotFoundError(f"Run extract.py first: {records_path}")

    records = json.loads(records_path.read_text(encoding="utf-8"))
    db_path = DATA_DIR / machine_id / "search.db"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE VIRTUAL TABLE records_fts USING fts5(
            record_id,
            machine,
            manual_type,
            system,
            title,
            body_text,
            smcs,
            keywords,
            content_type,
            tokenize='porter'
        )
    """)

    for r in records:
        conn.execute(
            """INSERT INTO records_fts
               (record_id, machine, manual_type, system, title, body_text, smcs, keywords, content_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r["id"],
                r["machine"],
                r["manual_type"],
                r["system"],
                r.get("title", ""),
                r.get("body_text", ""),
                " ".join(r.get("smcs", [])),
                " ".join(r.get("keywords", [])),
                r.get("content_type", ""),
            ),
        )

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM records_fts").fetchone()[0]
    conn.close()

    print(f"  {machine_id}: {count} records indexed → {db_path}")
    return {"machine_id": machine_id, "indexed": count, "db": str(db_path)}


def main():
    summaries = []
    for machine_id in MACHINES:
        summaries.append(build_index(machine_id))

    summary_path = DATA_DIR / "index_summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\nIndex build complete: {summary_path}")


if __name__ == "__main__":
    main()
