"""Parse tables from manual text into structured JSON (rows/columns)."""

import re
from pathlib import Path
from typing import Optional


def _clean_cell(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def parse_specification_table(text: str, table_id: str) -> Optional[dict]:
    """Parse spec tables: Temperature | Signal Voltage | Duty Cycle."""
    if "Table" not in text:
        return None

    m = re.search(
        r"Table\s*\d*\s*\n?(Specifications?.+?)\n(.+?)(?:\nTest\s+Step|\n\d+\.\s|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None

    header_block = m.group(1)
    body = m.group(2)
    columns = []
    for line in header_block.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("specification"):
            continue
        if re.search(r"(Temperature|Signal|Voltage|Duty|Pressure|Value|Step|Result)", line, re.I):
            parts = re.split(r"\s{2,}|\t", line)
            if len(parts) >= 2:
                columns = [_clean_cell(p) for p in parts if p.strip()]
                break

    if not columns:
        columns = ["Column 1", "Column 2", "Column 3"]

    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line or len(line) < 5:
            continue
        if re.search(r"(°C|°F|DCV|psi|kPa|MPa|%|mm|volt)", line, re.I):
            parts = re.split(r"\s{2,}|\t", line)
            if len(parts) >= 2:
                rows.append([_clean_cell(p) for p in parts])
            elif " " in line:
                rows.append([_clean_cell(line)])

    if rows:
        return {
            "table_id": table_id,
            "type": "specifications",
            "columns": columns[: max(len(columns), 2)],
            "rows": rows,
        }
    return None


def parse_test_steps_table(text: str, table_id: str) -> Optional[dict]:
    """Parse Test Step 1/2/3 procedure tables."""
    if not re.search(r"Test\s+Step\s+\d", text, re.I):
        return None

    rows = []
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        step_m = re.match(r"Test\s+Step\s+(\d+)[.:]?\s*(.*)", line, re.I)
        if step_m:
            if current:
                rows.append(current)
            current = {
                "step": step_m.group(1),
                "action": step_m.group(2) or "",
                "expected": "",
                "result": "",
            }
        elif current:
            if line.lower().startswith("expected result"):
                current["expected"] = line
            elif line.startswith("Results:") or line.startswith("OK -") or line.startswith("NOT OK"):
                current["result"] = (current["result"] + " " + line).strip()
            elif not line.startswith("STOP") and "Table" not in line:
                if not line.startswith("•"):
                    current["action"] = (current["action"] + " " + line).strip()

    if current:
        rows.append(current)

    if rows:
        return {
            "table_id": table_id,
            "type": "test_steps",
            "columns": ["Step", "Action", "Expected", "Result"],
            "rows": rows,
        }
    return None


def parse_contact_function_table(text: str, table_id: str) -> Optional[dict]:
    if "Contact" not in text or "Function" not in text:
        return None
    rows = []
    in_table = False
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"Contact\s+Function", line, re.I):
            in_table = True
            continue
        if in_table:
            m = re.match(r"^(\d+)\s+(.+)$", line)
            if m and int(m.group(1)) <= 30:
                rows.append({"contact": m.group(1), "function": m.group(2)})
            elif line.startswith("Table") or line.startswith("Note:"):
                break

    if rows:
        return {
            "table_id": table_id,
            "type": "contact_function",
            "columns": ["Contact", "Function"],
            "rows": rows,
        }
    return None


def parse_troubleshooting_table(text: str, table_id: str) -> Optional[dict]:
    """Parse Probable Cause / Recommended Actions style tables."""
    if not re.search(r"Probable\s+Cause|Recommended\s+Actions", text, re.I):
        return None

    rows = []
    causes = re.findall(
        r"(?:Probable\s+Cause[:\s]+)(.+?)(?=Recommended\s+Actions|Test\s+Step|\Z)",
        text,
        re.I | re.DOTALL,
    )
    actions = re.findall(
        r"(?:Recommended\s+Actions[:\s]+)(.+?)(?=Probable\s+Cause|Test\s+Step|\Z)",
        text,
        re.I | re.DOTALL,
    )

    if causes or actions:
        for i in range(max(len(causes), len(actions))):
            rows.append({
                "probable_cause": _clean_cell(causes[i])[:500] if i < len(causes) else "",
                "recommended_actions": _clean_cell(actions[i])[:500] if i < len(actions) else "",
            })

    if rows:
        return {
            "table_id": table_id,
            "type": "troubleshooting",
            "columns": ["Probable Cause", "Recommended Actions"],
            "rows": rows,
        }

    # Fallback: numbered test rows from troubleshooting section
    if re.search(r"Test\s+Steps?\s+.+Values?.+Results?", text, re.I):
        test_rows = []
        for m in re.finditer(
            r"(\d+)\.\s+(.+?)(?=\n\d+\.\s|\nExpected|\Z)",
            text,
            re.DOTALL,
        ):
            test_rows.append({
                "step": m.group(1),
                "description": _clean_cell(m.group(2))[:400],
            })
        if test_rows:
            return {
                "table_id": table_id,
                "type": "troubleshooting_steps",
                "columns": ["Step", "Description"],
                "rows": test_rows,
            }

    return None


def parse_generic_table_after_marker(text: str, table_id: str) -> Optional[dict]:
    """Parse any table block following 'Table N' label."""
    pattern = rf"{re.escape(table_id)}\s*\n(.+?)(?:\nTable\s+\d|\nTest\s+Step|\Z)"
    m = re.search(pattern, text, re.I | re.DOTALL)
    if not m:
        pattern = rf"{re.escape(table_id)}\s*\n(.+)"
        m = re.search(pattern, text, re.I | re.DOTALL)
    if not m:
        return None

    block = m.group(1).strip()
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None

    header = lines[0]
    columns = re.split(r"\s{2,}|\t", header) if re.search(r"\s{2,}", header) else [header]
    columns = [_clean_cell(c) for c in columns if c.strip()]

    rows = []
    for line in lines[1:]:
        if line.startswith("Note:") or line.startswith("STOP"):
            break
        parts = re.split(r"\s{2,}|\t", line) if re.search(r"\s{2,}", line) else [line]
        parts = [_clean_cell(p) for p in parts if p.strip()]
        if parts:
            rows.append(parts)

    if rows:
        return {
            "table_id": table_id,
            "type": "generic",
            "columns": columns if len(columns) > 1 else ["Value"],
            "rows": rows,
        }
    return None


def parse_table_before_label(text: str, table_id: str) -> Optional[dict]:
    """
    Caterpillar style: table data appears BEFORE the 'Table N' footer label.
    Example: header + rows, then 'Table 1' at end of section.
    """
    idx = text.rfind(table_id)
    if idx == -1:
        return None

    block = text[:idx].strip()
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None

    # Take lines after last Illustration block or last numbered step
    start = 0
    for i, line in enumerate(lines):
        if re.match(r"Illustration\s+\d+", line, re.I):
            start = i + 1
        elif re.match(r"^\d+\.\s*$", line) or re.match(r"^\d+\.$", line):
            start = i + 1

    segment = lines[start:]
    if len(segment) < 2:
        segment = lines[-8:]  # last few lines before label

    # Find header row (2+ columns separated by wide space or tab)
    header_idx = None
    columns = []
    for i, line in enumerate(segment):
        parts = re.split(r"\s{2,}|\t", line)
        parts = [_clean_cell(p) for p in parts if p.strip()]
        if len(parts) >= 2 and not re.match(r"^[\d.]+\s", line):
            header_idx = i
            columns = parts
            break

    if header_idx is None:
        # Single header line + data with units
        for i, line in enumerate(segment):
            if re.search(r"(Thickness|Pressure|Value|Step|Contact|Function|Cause|Action)", line, re.I):
                parts = re.split(r"\s{2,}|\t", line)
                if len(parts) >= 2:
                    header_idx = i
                    columns = [_clean_cell(p) for p in parts]
                    break

    if header_idx is None or not columns:
        return None

    rows = []
    for line in segment[header_idx + 1 :]:
        if re.match(r"Illustration", line, re.I):
            break
        parts = re.split(r"\s{2,}|\t", line)
        parts = [_clean_cell(p) for p in parts if p.strip()]
        if len(parts) >= 2:
            rows.append(parts)
        elif len(parts) == 1 and parts[0] and not parts[0].startswith("Table"):
            rows.append([parts[0]])

    if rows:
        return {
            "table_id": table_id,
            "type": "labeled_footer",
            "columns": columns,
            "rows": rows,
        }
    return None


def parse_procedure_numbered_table(text: str, table_id: str) -> Optional[dict]:
    """Numbered procedure steps 1. 2. 3. as a table."""
    rows = []
    for m in re.finditer(r"(?:^|\n)(\d+)\.\s+(.+?)(?=\n\d+\.\s|\nIllustration|\nTable\s+\d|\Z)", text, re.DOTALL):
        action = _clean_cell(m.group(2))
        if len(action) > 10:
            rows.append({"step": m.group(1), "action": action[:600]})
    if len(rows) >= 3:
        return {
            "table_id": table_id or "Procedure Steps",
            "type": "procedure_steps",
            "columns": ["Step", "Action"],
            "rows": rows,
        }
    return None


def _infer_procedure_section_title(action: str) -> str:
    action_lower = action.lower()
    rules = [
        (r"battery|main power switch|battery cables|charge the batteries|load test", "Batteries and Battery Cables"),
        (r"starting motor solenoid|start interlock", "Starting Motor Solenoid or Starting Circuit"),
        (r"starting motor|flywheel ring|pinion", "Starting Motor or Flywheel Ring Gear"),
        (r"driveline|engine accessories", "Transmission or Engine Accessories"),
        (r"hydraulic cylinder lock|unit injectors", "Hydraulic Cylinder Lock"),
        (r"fuel level|fuel lines|fuel tank|prime the fuel", "Fuel Supply"),
        (r"diagnostic codes|event codes|cat et|caterpillar electronic technician", "Diagnostic Codes and ECM"),
        (r"engine speed|timing reference|injector solenoid", "Engine Speed/Timing and Injectors"),
        (r"electrical connectors|battery voltage at the ecm|unswitched \+battery", "Electrical Power Supply to ECM"),
        (r"part number|digital multimeter|tools needed", "Tools Needed"),
        (r"oil cooler fan|hydraulic oil temperature", "Hydraulic Oil Cooling"),
        (r"overheat|coolant temperature", "Engine Cooling"),
    ]
    for pattern, title in rules:
        if re.search(pattern, action_lower):
            return title
    return "Procedure Steps"


def _extract_trailing_section_title(action: str) -> Optional[str]:
    """Section name often appended to the previous step's action text."""
    m = re.search(
        r"\.\s+([A-Z][A-Za-z0-9 /\-()]+(?:\([^)]+\))?)\s*(?:\d{2}/\d{2}/\d{4}|$)",
        action,
    )
    if not m:
        return None
    title = _clean_cell(m.group(1))
    if 8 <= len(title) <= 80:
        return title
    return None


def split_procedure_steps_table(table: dict) -> list[dict]:
    """Split combined procedure tables when step numbering resets to 1."""
    if table.get("type") != "procedure_steps":
        return [table]

    rows = table.get("rows") or []
    if len(rows) < 4:
        return [table]

    sections: list[tuple[str, list]] = []
    current: list = []
    section_title = table.get("title") or "Procedure Steps"

    for row in rows:
        step = str(row.get("step", ""))
        if step == "1" and current:
            sections.append((section_title, current))
            section_title = _infer_procedure_section_title(row.get("action", ""))
            current = [row]
        else:
            if step == "1" and not current:
                section_title = _infer_procedure_section_title(row.get("action", ""))
            current.append(row)

    if current:
        sections.append((section_title, current))

    if len(sections) <= 1:
        return [table]

    result = []
    for title, sec_rows in sections:
        if not sec_rows:
            continue
        safe_id = re.sub(r"\s+", " ", title).strip()[:60]
        result.append({
            **table,
            "table_id": f"Procedure: {safe_id}",
            "title": title,
            "rows": sec_rows,
        })
    return result or [table]


def tag_tools_table(table: dict) -> dict:
    """Mark parts/tools tables so the UI can deprioritize them."""
    columns = " ".join(table.get("columns") or []).lower()
    if "part number" in columns or "tools needed" in columns:
        table = {**table, "type": "tools", "title": table.get("title") or "Tools Needed"}
    return table


def finalize_tables(tables: list[dict]) -> list[dict]:
    """Split long procedure tables and tag tools tables."""
    out: list[dict] = []
    for tbl in tables:
        for split in split_procedure_steps_table(tbl):
            out.append(tag_tools_table(split))
    return out


def extract_tables_pdfplumber(pdf_path: Path, page_num: int) -> list[dict]:
    """Fallback: extract tables directly from PDF layout using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        return []

    tables = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            if page_num < 1 or page_num > len(pdf.pages):
                return []
            raw = pdf.pages[page_num - 1].extract_tables()
            for i, tbl in enumerate(raw or []):
                if not tbl or len(tbl) < 2:
                    continue
                header = [_clean_cell(c or "") for c in tbl[0]]
                if not any(header):
                    header = [f"Col{j+1}" for j in range(len(tbl[0]))]
                rows = []
                for row in tbl[1:]:
                    cells = [_clean_cell(c or "") for c in row]
                    if any(cells):
                        rows.append(cells)
                if rows:
                    tables.append({
                        "table_id": f"Table {i + 1}",
                        "type": "pdfplumber",
                        "columns": header,
                        "rows": rows,
                    })
    except Exception:
        pass
    return tables


def parse_all_tables_from_text(text: str) -> list[dict]:
    """Find and parse all tables referenced in a text block."""
    tables = []
    table_ids = list(dict.fromkeys(re.findall(r"\bTable\s+(\d+)\b", text, re.I)))

    if not table_ids:
        # Procedure-only content without Table label
        proc = parse_procedure_numbered_table(text, "Procedure Steps")
        if proc:
            return finalize_tables([proc])
        return []

    for num in table_ids:
        table_id = f"Table {num}"
        parsed = (
            parse_table_before_label(text, table_id)
            or parse_test_steps_table(text, table_id)
            or parse_specification_table(text, table_id)
            or parse_contact_function_table(text, table_id)
            or parse_troubleshooting_table(text, table_id)
            or parse_generic_table_after_marker(text, table_id)
            or parse_procedure_numbered_table(text, table_id)
        )
        if parsed and parsed.get("rows"):
            tables.append(parsed)

    return finalize_tables(tables)
