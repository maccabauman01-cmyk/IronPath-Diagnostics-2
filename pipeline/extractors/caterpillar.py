"""Caterpillar manual PDF extractor (D11T, 785D)."""

from pathlib import Path

from pypdf import PdfReader

MAX_PAGES_PER_RECORD = 8

from .base import (
    ManualRecord,
    clean_text,
    detect_content_type,
    extract_title,
    is_new_procedure_page,
    make_record_id,
    parse_illustrations,
    parse_smcs,
    parse_tables,
    SENR_PATTERN,
    UENR_PATTERN,
)


def infer_manual_type(pdf_path: Path, machine_config: dict) -> str:
    parts = pdf_path.parts
    for folder_name, manual_type in machine_config["manual_type_map"].items():
        if folder_name in parts:
            return manual_type
    return "general"


def infer_system(pdf_path: Path, machine_source: Path) -> str:
    try:
        rel = pdf_path.relative_to(machine_source)
        parts = list(rel.parts)
        if len(parts) >= 2:
            return "/".join(parts[:-1])
        return parts[0].replace(".pdf", "") if parts else "general"
    except ValueError:
        return "general"


def extract_pdf(
    pdf_path: Path,
    machine_id: str,
    machine_config: dict,
) -> list[ManualRecord]:
    reader = PdfReader(str(pdf_path))
    manual_type = infer_manual_type(pdf_path, machine_config)
    system = infer_system(pdf_path, machine_config["source_dir"])
    source_file = str(pdf_path.relative_to(machine_config["source_dir"]))

    records: list[ManualRecord] = []
    current_pages: list[tuple[int, str]] = []

    def flush():
        if not current_pages:
            return
        combined = "\n\n".join(t for _, t in current_pages)
        page_start = current_pages[0][0]
        page_end = current_pages[-1][0]
        smcs = parse_smcs(combined)
        illustrations = []
        tables = []
        for pg, txt in current_pages:
            illustrations.extend(parse_illustrations(txt, pg))
            tables.extend(parse_tables(txt, pg))

        content_type = detect_content_type(combined, manual_type)
        senr = SENR_PATTERN.search(combined)
        uenr = UENR_PATTERN.search(combined)

        record = ManualRecord(
            id=make_record_id(machine_id, source_file, page_start),
            machine=machine_id,
            manual_type=manual_type,
            system=system,
            source_file=source_file,
            page_start=page_start,
            page_end=page_end,
            smcs=smcs,
            doc_ref="",
            senr_ref=senr.group(0) if senr else "",
            uenr_ref=uenr.group(0) if uenr else "",
            title=extract_title(combined, system),
            body_text=combined,
            illustrations=illustrations,
            tables=tables,
            content_type=content_type,
            has_troubleshooting_table=content_type == "troubleshooting_table",
        )
        records.append(record)
        current_pages.clear()

    for i, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        text = clean_text(raw)
        if not text.strip():
            continue

        if current_pages and is_new_procedure_page(text, "caterpillar"):
            flush()

        if len(current_pages) >= MAX_PAGES_PER_RECORD:
            flush()

        current_pages.append((i, text))

    flush()
    return records
