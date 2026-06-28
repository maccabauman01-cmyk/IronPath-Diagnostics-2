"""Parse structured data from extracted manual text."""

import re
from typing import Optional

FAULT_CODE_PATTERN = re.compile(
    r"(?P<code>\d{6}-\d{2})\s+(?P<name>.+?)(?=\n\d{6}-\d{2}\s|\Z)",
    re.DOTALL,
)

FAULT_CODE_LINE = re.compile(r"^(?P<code>\d{6}-\d{2})\s+(?P<name>.+)$", re.MULTILINE)

TABLE_HEADER_PATTERN = re.compile(
    r"(Test\s+Steps|Probable\s+Cause|Contact\s+Function|Values|Results)",
    re.IGNORECASE,
)


def parse_hitachi_fault_codes(text: str) -> list[dict]:
    """Parse Hitachi fault code blocks from fault-codes PDF text."""
    codes: list[dict] = []
    seen: set[str] = set()

    # Split on 6-digit-2-digit fault code pattern at line start
    parts = re.split(r"(?=\n\d{6}-\d{2}\s)", "\n" + text)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"(\d{6}-\d{2})\s+(.+)", part, re.DOTALL)
        if not m:
            continue
        code = m.group(1)
        if code in seen:
            continue
        seen.add(code)
        rest = m.group(2).strip()

        # Split rest into name, condition, symptom, remedy heuristically
        lines = [ln.strip() for ln in rest.splitlines() if ln.strip()]
        name = lines[0] if lines else ""
        remedy_lines = []
        symptom_lines = []
        condition_lines = []
        section = "condition"

        for line in lines[1:]:
            low = line.lower()
            if line.startswith("- ") or line.startswith("•"):
                remedy_lines.append(line.lstrip("-• ").strip())
                section = "remedy"
            elif "cannot be" in low or "does not" in low or "nil action" in low:
                symptom_lines.append(line)
                section = "symptom"
            elif section == "condition" and not remedy_lines:
                condition_lines.append(line)
            elif section == "symptom":
                symptom_lines.append(line)
            else:
                condition_lines.append(line)

        codes.append({
            "code": code,
            "name": name[:200],
            "condition": " ".join(condition_lines)[:500],
            "symptom": " ".join(symptom_lines)[:500],
            "remedy": " | ".join(remedy_lines)[:500],
        })

    return codes


def parse_table_from_text(text: str, table_id: str = "Table 1") -> Optional[dict]:
    """Attempt to parse a simple table from manual text."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Caterpillar test step table
    if re.search(r"Test\s+Step\s+\d", text, re.IGNORECASE):
        rows = []
        current_step = None
        for line in lines:
            step_m = re.match(r"Test\s+Step\s+(\d+)[.:]\s*(.+)", line, re.IGNORECASE)
            if step_m:
                if current_step:
                    rows.append(current_step)
                current_step = {
                    "step": step_m.group(1),
                    "description": step_m.group(2),
                    "expected": "",
                    "result": "",
                }
            elif current_step:
                if line.startswith("Expected Result"):
                    current_step["expected"] = line
                elif line.startswith("Results:") or line.startswith("OK -") or line.startswith("NOT OK"):
                    current_step["result"] = line
                elif not line.startswith("STOP"):
                    current_step["description"] += " " + line
        if current_step:
            rows.append(current_step)
        if rows:
            return {
                "table_id": table_id,
                "type": "test_steps",
                "columns": ["Step", "Description", "Expected", "Result"],
                "rows": rows,
            }

    # Simple two-column contact/function table
    if "Contact Function" in text or re.search(r"^Contact\s+Function", text, re.MULTILINE):
        rows = []
        for line in lines:
            m = re.match(r"^(\d+)\s+(.+)$", line)
            if m and m.group(1).isdigit() and int(m.group(1)) <= 20:
                rows.append({"contact": m.group(1), "function": m.group(2)})
        if rows:
            return {
                "table_id": table_id,
                "type": "contact_function",
                "columns": ["Contact", "Function"],
                "rows": rows,
            }

    # Probable cause table hint
    if "Probable Cause" in text and "Recommended Actions" in text:
        return {
            "table_id": table_id,
            "type": "troubleshooting",
            "columns": ["Probable Cause", "Recommended Actions"],
            "rows": [],
            "raw_hint": True,
        }

    return None
