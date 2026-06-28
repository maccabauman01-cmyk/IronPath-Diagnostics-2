"""Hitachi manual PDF extractor (EX3600-7)."""

from pathlib import Path

from pypdf import PdfReader

from .base import (
    ManualRecord,
    clean_text,
    detect_content_type,
    extract_title,
    make_record_id,
    parse_illustrations,
    parse_smcs,
    parse_tables,
)


def infer_manual_type(pdf_path: Path, machine_config: dict) -> str:
    name = pdf_path.name
    return machine_config["manual_type_map"].get(name, "general")


def extract_pdf(
    pdf_path: Path,
    machine_id: str,
    machine_config: dict,
) -> list[ManualRecord]:
    reader = PdfReader(str(pdf_path))
    manual_type = infer_manual_type(pdf_path, machine_config)
    system = pdf_path.stem
    source_file = pdf_path.name

    # Hitachi consolidated PDFs: group ~3 pages per record
    chunk_size = 3
    records: list[ManualRecord] = []
    pages: list[tuple[int, str]] = []

    for i, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        text = clean_text(raw)
        if text.strip():
            pages.append((i, text))

    for start in range(0, len(pages), chunk_size):
        chunk = pages[start : start + chunk_size]
        combined = "\n\n".join(t for _, t in chunk)
        page_start = chunk[0][0]
        page_end = chunk[-1][0]

        illustrations = []
        tables = []
        for pg, txt in chunk:
            illustrations.extend(parse_illustrations(txt, pg))
            tables.extend(parse_tables(txt, pg))

        content_type = detect_content_type(combined, manual_type)

        records.append(
            ManualRecord(
                id=make_record_id(machine_id, source_file, page_start),
                machine=machine_id,
                manual_type=manual_type,
                system=system,
                source_file=source_file,
                page_start=page_start,
                page_end=page_end,
                smcs=parse_smcs(combined),
                title=extract_title(combined, system),
                body_text=combined,
                illustrations=illustrations,
                tables=tables,
                content_type=content_type,
                has_troubleshooting_table=content_type == "troubleshooting_table",
            )
        )

    return records
