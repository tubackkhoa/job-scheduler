THEME = {
    "positive": "#28a745",
    "negative": "#dc3545",
    "neutral": "#6c757d",
    "warning": "#ffc107",
}


def color_span(text: str, color: str, bold: bool = False) -> str:
    weight = "font-weight:bold;" if bold else ""
    return f"<span style='color:{color};{weight}'>{text}</span>"
