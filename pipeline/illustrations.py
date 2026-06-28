"""Extract embedded diagram images from PDF manuals — target 100% coverage."""

import re
from pathlib import Path

import fitz

DPI = 144
SCALE = DPI / 72


def collect_illustration_refs(records: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    refs = []
    for r in records:
        sf = r["source_file"]
        for ill in r.get("illustrations", []):
            key = (sf, ill["page"], ill["id"])
            if key not in seen:
                seen.add(key)
                refs.append({"source_file": sf, "page": ill["page"], "id": ill["id"]})
        # Also pick up illustration IDs from body text if missing from array
        for m in re.finditer(r"Illustration\s+\d+\s+([a-z]\d+)", r.get("body_text", ""), re.I):
            key = (sf, r["page_start"], m.group(1))
            if key not in seen:
                seen.add(key)
                refs.append({"source_file": sf, "page": r["page_start"], "id": m.group(1)})
    return refs


def _save_pix(pix: fitz.Pixmap, path: Path) -> bool:
    if pix.width < 40 or pix.height < 40:
        return False
    pix.save(str(path))
    return True


def _extract_all_embedded(page: fitz.Page, doc: fitz.Document, out_dir: Path, ill_id: str) -> str | None:
    """Try every embedded image on page; save largest valid one."""
    best = None
    best_area = 0
    for img in page.get_images(full=True):
        try:
            pix = fitz.Pixmap(doc, img[0])
            if pix.n - pix.alpha > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            area = pix.width * pix.height
            if area > best_area and area >= 2_500:
                best_area = area
                best = pix
        except Exception:
            continue
    if best:
        path = out_dir / f"{ill_id}.png"
        if _save_pix(best, path):
            return path.name
    return None


def _extract_by_image_blocks(page: fitz.Page, doc: fitz.Document, out_dir: Path, ill_id: str) -> str | None:
    """Use get_image_info bboxes to clip and render each image region."""
    for idx, info in enumerate(page.get_image_info()):
        try:
            bbox = fitz.Rect(info["bbox"])
            if bbox.width < 30 or bbox.height < 30:
                continue
            mat = fitz.Matrix(SCALE, SCALE)
            pix = page.get_pixmap(matrix=mat, clip=bbox, alpha=False)
            path = out_dir / (f"{ill_id}.png" if idx == 0 else f"{ill_id}_{idx}.png")
            if _save_pix(pix, path):
                return path.name
        except Exception:
            continue
    return None


def _render_illustration_region(page: fitz.Page, out_dir: Path, ill_id: str) -> str | None:
    """
  Fallback for vector-drawn diagrams (no embedded raster).
  Renders the diagram area below the 'Illustration' caption.
  """
    y_top = page.rect.y0
    found = False
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if re.search(r"Illustration\s+\d+", span.get("text", ""), re.I):
                    y_top = span["bbox"][1]
                    found = True
                    break

    if not found:
        y_top = page.rect.y0 + page.rect.height * 0.08

    y_bottom = min(page.rect.y1, y_top + page.rect.height * 0.62)
    clip = fitz.Rect(page.rect.x0 + 10, y_top, page.rect.x1 - 10, y_bottom)
    if clip.height < 50:
        clip = fitz.Rect(page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y0 + page.rect.height * 0.65)

    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE), clip=clip, alpha=False)
        path = out_dir / f"{ill_id}.png"
        if _save_pix(pix, path):
            return path.name
    except Exception:
        pass
    return None


def extract_illustration(
    page: fitz.Page, doc: fitz.Document, out_dir: Path, ill_id: str
) -> str | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for method in (_extract_all_embedded, _extract_by_image_blocks, _render_illustration_region):
        if method == _render_illustration_region:
            result = _render_illustration_region(page, out_dir, ill_id)
        elif method == _extract_by_image_blocks:
            result = _extract_by_image_blocks(page, doc, out_dir, ill_id)
        else:
            result = _extract_all_embedded(page, doc, out_dir, ill_id)
        if result:
            return result
    return None


def extract_hitachi_page_figures(
    source_dir: Path,
    records: list[dict],
    out_dir: Path,
    force: bool = False,
) -> dict[str, str]:
    """
    Hitachi manuals don't use g0xxxx illustration IDs.
    Extract all embedded images per page and index by page key.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    index: dict[str, str] = {}
    pdf_cache: dict[str, fitz.Document] = {}

    pages_needed: set[tuple[str, int]] = set()
    for r in records:
        for p in range(r["page_start"], r["page_end"] + 1):
            pages_needed.add((r["source_file"], p))

    for sf, page_num in sorted(pages_needed):
        pdf_path = source_dir / sf
        if not pdf_path.exists():
            continue
        if sf not in pdf_cache:
            pdf_cache[sf] = fitz.open(str(pdf_path))
        doc = pdf_cache[sf]
        page = doc[page_num - 1]
        images = page.get_images(full=True)

        for img_idx, img in enumerate(images):
            key = f"{sf}:{page_num}:{img_idx}"
            fname = f"{sf.replace('/', '__').replace('.pdf','')}__p{page_num}__img{img_idx}.png"
            out_path = out_dir / fname
            rel = f"assets/illustrations/{fname}"

            if out_path.exists() and not force:
                index[key] = rel
                continue
            try:
                pix = fitz.Pixmap(doc, img[0])
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                if pix.width < 50 or pix.height < 50:
                    continue
                if _save_pix(pix, out_path):
                    index[key] = rel
            except Exception:
                # Render page region fallback for vector pages with diagram
                if img_idx == 0 and key not in index:
                    rendered = _render_illustration_region(page, out_dir, f"p{page_num}_fig")
                    if rendered:
                        index[f"{sf}:{page_num}:0"] = f"assets/illustrations/{rendered}"

    for doc in pdf_cache.values():
        doc.close()
    return index


def extract_all_illustrations(
    machine_id: str,
    manufacturer: str,
    source_dir: Path,
    records: list[dict],
    out_dir: Path,
    force: bool = False,
) -> dict[str, str]:
    """Returns illustration_id -> relative image path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    index: dict[str, str] = {}

    if manufacturer == "hitachi":
        page_index = extract_hitachi_page_figures(source_dir, records, out_dir, force=force)
        # Also map page keys for enrich step
        index["_page_index"] = ""  # marker; real data in page_index file
        hitachi_path = out_dir.parent / "hitachi_page_index.json"
        hitachi_path.write_text(__import__("json").dumps(page_index, indent=2))
        return index

    refs = collect_illustration_refs(records)
    pdf_cache: dict[str, fitz.Document] = {}

    for ref in refs:
        ill_id = ref["id"]
        rel = f"assets/illustrations/{ill_id}.png"
        out_path = out_dir / f"{ill_id}.png"

        if out_path.exists() and not force:
            index[ill_id] = rel
            continue

        sf, page_num = ref["source_file"], ref["page"]
        pdf_path = source_dir / sf
        if not pdf_path.exists():
            continue

        try:
            if sf not in pdf_cache:
                pdf_cache[sf] = fitz.open(str(pdf_path))
            page = pdf_cache[sf][page_num - 1]
            saved = extract_illustration(page, pdf_cache[sf], out_dir, ill_id)
            if saved:
                index[ill_id] = f"assets/illustrations/{saved}"
        except Exception:
            pass

    for doc in pdf_cache.values():
        doc.close()
    return index
