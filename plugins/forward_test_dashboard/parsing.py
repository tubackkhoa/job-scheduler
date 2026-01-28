from typing import Optional, Dict, Any


def parse_table_message(message: str) -> Optional[Dict[str, Any]]:
    """Parse table message from logs (Python version of JS parseTableMessage)."""
    if not message:
        return None

    import re

    cleaned = message.strip()
    cleaned = re.sub(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\[.*?\]\s+", "", cleaned)

    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    if len(lines) < 2:
        return None

    header = [h for h in lines[0].split() if h]
    if len(header) < 2:
        return None

    pred_time_index = -1
    for i, col in enumerate(header):
        if col.lower() == "pred_time":
            pred_time_index = i
            break

    data_rows = []
    for i in range(1, len(lines)):
        line = lines[i]
        if not line or len(line) < 3:
            continue

        cells = [c for c in line.split() if c]

        if cells and re.match(r"^\d+$", cells[0]):
            cells = cells[1:]

        if pred_time_index >= 0 and pred_time_index < len(cells) - 1:
            date_pattern = r"^\d{4}-\d{2}-\d{2}$"
            time_pattern = r"^\d{2}:\d{2}:\d{2}$"

            if re.match(date_pattern, cells[pred_time_index]) and re.match(
                time_pattern, cells[pred_time_index + 1]
            ):
                cells[pred_time_index] = f"{cells[pred_time_index]} {cells[pred_time_index + 1]}"
                cells.pop(pred_time_index + 1)

        while len(cells) < len(header):
            cells.append("")
        cells = cells[: len(header)]

        if len(cells) >= min(len(header), 2):
            data_rows.append(cells)

    if not data_rows:
        return None

    return {"header": header, "rows": data_rows}


def extract_model_key(job) -> str | None:
    cfg = job.get("config") or {}
    if isinstance(cfg, str):
        import json

        cfg = json.loads(cfg)
    return cfg.get("model_key")

