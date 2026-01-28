from typing import Optional, Dict, Any


def parse_table_message(message: str) -> Optional[Dict[str, Any]]:
    if not message:
        return None

    lines = [l.strip() for l in message.splitlines() if l.strip()]
    if len(lines) < 2:
        return None

    header_idx = next(
        (i for i, line in enumerate(lines) if ":" not in line and len(line.split()) >= 2),
        None,
    )

    if header_idx is None or header_idx + 1 >= len(lines):
        return None

    header = lines[header_idx].split()
    rows = []

    for line in lines[header_idx + 1 :]:
        cells = line.split()
        if len(cells) > len(header):
            cells = [" ".join(cells[:2])] + cells[2:]

        rows.append((cells + [""] * len(header))[: len(header)])
    for row in rows:
        row[0] = row[0].split(" ")[1]
    return {"header": header, "rows": rows}


def extract_model_key(job) -> str | None:
    cfg = job.get("config") or {}
    if isinstance(cfg, str):
        import json

        cfg = json.loads(cfg)
    return cfg.get("model_key")
