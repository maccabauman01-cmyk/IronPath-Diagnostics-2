"""Shared extraction utilities."""

import hashlib
import re
from dataclasses import dataclass, field, asdict
from typing import Optional


SMCS_PATTERN = re.compile(r"SMCS\s*-\s*([\d,\s]+)", re.IGNORECASE)
ILLUSTRATION_PATTERN = re.compile(
    r"Illustration\s+(\d+)\s+([a-z]\d+)", re.IGNORECASE
)
TABLE_PATTERN = re.compile(r"Table\s+(\d+)", re.IGNORECASE)
DOC_ID_PATTERN = re.compile(r"^(i\d+)", re.MULTILINE)
UENR_PATTERN = re.compile(r"UENR\d+[-\d]*", re.IGNORECASE)
SENR_PATTERN = re.compile(r"SENR\d+[-\d]*", re.IGNORECASE)
PROBABLE_CAUSE_PATTERN = re.compile(
    r"Probable\s+Cause|Recommended\s+Actions|Test\s+Steps", re.IGNORECASE
)
FAULT_CODE_PATTERN = re.compile(r"fault\s*code|diagnostic\s*code", re.IGNORECASE)


@dataclass
class IllustrationRef:
    label: str
    id: str
    page: int


@dataclass
class TableRef:
    table_id: str
    page: int
    caption: str = ""


@dataclass
class ManualRecord:
    id: str
    machine: str
    manual_type: str
    system: str
    source_file: str
    page_start: int
    page_end: int
    smcs: list[str] = field(default_factory=list)
    doc_ref: str = ""
    senr_ref: str = ""
    uenr_ref: str = ""
    title: str = ""
    body_text: str = ""
    keywords: list[str] = field(default_factory=list)
    illustrations: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    content_type: str = "general"
    has_troubleshooting_table: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def make_record_id(machine: str, source_file: str, page_start: int, suffix: str = "") -> str:
    raw = f"{machine}:{source_file}:{page_start}:{suffix}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def parse_smcs(text: str) -> list[str]:
    codes = []
    for match in SMCS_PATTERN.findall(text):
        for part in match.replace(",", " ").split():
            part = part.strip()
            if part.isdigit():
                codes.append(part)
    return list(dict.fromkeys(codes))


def parse_illustrations(text: str, page: int) -> list[dict]:
    refs = []
    for match in ILLUSTRATION_PATTERN.finditer(text):
        refs.append({
            "label": f"Illustration {match.group(1)}",
            "id": match.group(2),
            "page": page,
        })
    return refs


def parse_tables(text: str, page: int) -> list[dict]:
    refs = []
    seen = set()
    for match in TABLE_PATTERN.finditer(text):
        tid = f"Table {match.group(1)}"
        if tid not in seen:
            seen.add(tid)
            refs.append({"table_id": tid, "page": page})
    return refs


def detect_content_type(text: str, manual_type: str) -> str:
    if PROBABLE_CAUSE_PATTERN.search(text):
        return "troubleshooting_table"
    if manual_type == "troubleshooting":
        return "troubleshooting"
    if manual_type == "testing-and-adjusting":
        return "test_procedure"
    if manual_type == "fault-codes":
        return "fault_code"
    if manual_type == "system-operation":
        return "system_description"
    return "general"


def extract_title(text: str, system: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines[:8]:
        if line.startswith("i") and "SMCS" in line:
            continue
        if "SIS 2.0" in line or "©" in line or line.startswith("http"):
            continue
        if len(line) > 15 and not line.startswith("PSP-"):
            return line[:200]
    return system or "Untitled section"


def is_new_procedure_page(text: str, manufacturer: str) -> bool:
    if manufacturer == "caterpillar":
        head = text.strip()[:600]
        if re.search(r"^i\d+SMCS", head, re.MULTILINE):
            return True
        lines = [ln.strip() for ln in head.splitlines() if ln.strip()][:12]
        for line in lines:
            if re.match(r"^i\d+$", line):
                return True
            if re.match(r"^i\d+", line) and "SMCS" in line:
                return True
        return False
    if manufacturer == "hitachi":
        return bool(re.search(r"^[A-Z0-9]{2,}-\d+", text.strip()[:100]))
    return False


def clean_text(text: str) -> str:
    lines = []
    skip_patterns = (
        "SIS 2.0",
        "sis2.cat.com",
        "© 20",
        "Caterpillar Inc",
        "PSP-0007",
        "Media Search -",
        "Page ",
        "of 5Media Search",
    )
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(p in stripped for p in skip_patterns):
            continue
        lines.append(stripped)
    return "\n".join(lines)
