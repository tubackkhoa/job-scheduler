import re
from typing import Optional, Dict, Any


def parse_table_message(message: str) -> Optional[Dict[str, Any]]:
    if not message:
        return None

    message = re.sub(r"^\d{4}-\d{2}-\d{2}.*?\]\s+", "", message.strip())
    lines = [l.strip() for l in message.splitlines() if l.strip()]
    if len(lines) < 2:
        return None

    header = lines[0].split()
    rows = []

    for line in lines[1:]:
        cells = line.split()
        if cells and cells[0].isdigit():
            cells = cells[1:]
        rows.append((cells + [""] * len(header))[: len(header)])

    return {"header": header, "rows": rows}
