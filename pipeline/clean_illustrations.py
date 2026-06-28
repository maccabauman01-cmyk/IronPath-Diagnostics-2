#!/usr/bin/env python3
"""
Detect and quarantine junk illustration PNGs (page bars, blank strips, corrupt files).

Typical junk: thin horizontal bars extracted from PDF headers/footers (e.g. 375×72, 493×47).

Usage:
  python pipeline/clean_illustrations.py              # dry-run report
  python pipeline/clean_illustrations.py --apply      # quarantine + update records
  python pipeline/clean_illustrations.py --apply --rebuild
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from pipeline.config import DATA_DIR, MACHINES


def analyze_image(path: Path) -> dict:
    """Return metadata and junk classification for one PNG."""
    try:
        with Image.open(path) as im:
            im.load()
            gray = im.convert("L")
            w, h = gray.size
    except Exception as exc:
        return {
            "path": str(path.name),
            "valid": False,
            "reason": f"corrupt: {exc}",
            "is_junk": True,
        }

    pixels = gray.getdata()
    n = max(len(pixels), 1)
    mean = sum(pixels) / n
    var = sum((p - mean) ** 2 for p in pixels) / n
    aspect = w / max(h, 1)

    reasons: list[str] = []

    # Thin horizontal bar (page header/footer artifact)
    if aspect >= 3.5 and h <= 100:
        reasons.append(f"horizontal_bar ({w}x{h}, aspect={aspect:.1f})")

    # Very small thumbnail-like noise
    if w < 40 or h < 40:
        reasons.append(f"tiny ({w}x{h})")

    # Nearly blank white strip
    if var < 80 and mean > 210 and aspect > 2:
        reasons.append(f"blank_strip (var={var:.0f})")

    # Extremely low detail + wide
    if var < 200 and aspect > 5 and h < 120:
        reasons.append(f"low_detail_bar (var={var:.0f})")

    is_junk = len(reasons) > 0

    return {
        "path": path.name,
        "valid": True,
        "width": w,
        "height": h,
        "aspect": round(aspect, 2),
        "variance": round(var, 1),
        "mean": round(mean, 1),
        "is_junk": is_junk,
        "reasons": reasons,
    }


def clean_machine(machine_id: str, apply: bool) -> dict:
    data_dir = DATA_DIR / machine_id
    ill_dir = data_dir / "assets" / "illustrations"
    junk_dir = ill_dir / "_junk"

    if not ill_dir.exists():
        return {"machine_id": machine_id, "error": "no illustrations folder"}

    junk_files: set[str] = set()
    report: list[dict] = []

    for png in sorted(ill_dir.glob("*.png")):
        info = analyze_image(png)
        if info.get("is_junk"):
            junk_files.add(png.name)
            report.append(info)

    records_path = data_dir / "records.json"
    records = json.loads(records_path.read_text(encoding="utf-8"))
    removed_refs = 0

    for r in records:
        kept = []
        for ill in r.get("illustrations", []):
            rel = ill.get("image_path", "")
            fname = Path(rel).name if rel else ""
            if fname in junk_files:
                removed_refs += 1
                continue
            kept.append(ill)
        r["illustrations"] = kept

    moved = 0
    if apply:
        junk_dir.mkdir(parents=True, exist_ok=True)
        for fname in junk_files:
            src = ill_dir / fname
            dst = junk_dir / fname
            if src.exists():
                shutil.move(str(src), str(dst))
                moved += 1
        records_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {
        "machine_id": machine_id,
        "total_pngs": len(list(ill_dir.glob("*.png"))) + (moved if apply else 0),
        "junk_count": len(junk_files),
        "removed_refs": removed_refs,
        "moved": moved,
        "applied": apply,
        "samples": report[:8],
    }


def main():
    parser = argparse.ArgumentParser(description="Clean junk illustration PNGs")
    parser.add_argument("--machine", choices=list(MACHINES.keys()))
    parser.add_argument("--apply", action="store_true", help="Quarantine junk and update records.json")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild watermelon seeds + search index after clean")
    args = parser.parse_args()

    ids = [args.machine] if args.machine else list(MACHINES.keys())
    summaries = []

    for mid in ids:
        result = clean_machine(mid, apply=args.apply)
        summaries.append(result)
        junk = result.get("junk_count", 0)
        total = result.get("total_pngs", 0)
        pct = f"{100 * junk / total:.1f}%" if total else "n/a"
        mode = "APPLIED" if args.apply else "DRY-RUN"
        print(f"\n[{mode}] {mid}: {junk} junk / {total} images ({pct})")
        if result.get("removed_refs"):
            print(f"  illustration refs removed from records: {result['removed_refs']}")
        for s in result.get("samples", []):
            print(f"  - {s['path']}: {', '.join(s.get('reasons', [s.get('reason', '?')]))}")

    summary_path = DATA_DIR / "illustration_clean_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "applied": args.apply,
                "machines": summaries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSummary: {summary_path}")

    if args.apply and args.rebuild:
        print("\nRebuilding Watermelon seeds…")
        from pipeline.build_watermelon_seed import build_machine

        for mid in ids:
            build_machine(mid)

        print("Rebuilding search indexes…")
        from pipeline.build_index import build_index

        for mid in ids:
            build_index(mid)

        print("Done.")


if __name__ == "__main__":
    main()
