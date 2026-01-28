from typing import Optional, Dict, Any


def parse_table_message(message: str) -> Optional[Dict[str, Any]]:
    if not message:
        return None

    lines = [l.strip() for l in message.splitlines() if l.strip()]
    if len(lines) < 2:
        return None

    header_idx = None
    for i, line in enumerate(lines):
        if ":" in line:  # skip banner lines
            continue
        cols = line.split()
        if len(cols) >= 2:
            header_idx = i
            break

    if header_idx is None or header_idx + 1 >= len(lines):
        return None

    header = lines[header_idx].split()
    rows = []

    for line in lines[header_idx + 1 :]:
        cells = line.split()

        # merge date + time
        if len(cells) > len(header):
            cells = [" ".join(cells[:2])] + cells[2:]

        rows.append((cells + [""] * len(header))[: len(header)])

    return {"header": header, "rows": rows}
