from .theme import THEME, color_span


def fmt_pnl(v):
    if v is None:
        return "-"
    if v > 0:
        return color_span(f"↗ +${v:.4f}", THEME["positive"], bold=True)
    if v < 0:
        return color_span(f"↘ ${v:.4f}", THEME["negative"], bold=True)
    return color_span("$0.0000", THEME["neutral"])


def fmt_status(status):
    if not status:
        return "-"
    if status["state"] == "active":
        return color_span(f"✓ Active ({status['label']})", THEME["positive"])
    if status["state"] == "inactive":
        return color_span(f"⏸ Inactive ({status['label']})", THEME["warning"])
    return color_span("⊘ No Job", THEME["neutral"])


def fmt_latest(latest):
    if not latest:
        return "-"
    color = THEME["positive"] if latest["direction"] in ("BUY", "LONG") else THEME["negative"]
    return f"{color_span(latest['symbol'], color, bold=True)} {fmt_pnl(latest['pnl'])}"


def fmt_winrate(winrate):
    if winrate is None:
        return "-"
    
    winrate_pct = winrate * 100
    
    if winrate_pct >= 50:
        color = THEME["positive"]
    elif winrate_pct >= 40:
        color = THEME["neutral"]
    else:
        color = THEME["negative"]
    
    return color_span(f"{winrate_pct:.1f}%", color, bold=True)


def fmt_drawdown(drawdown):
    """Format max drawdown as negative percentage."""
    if drawdown is None or drawdown == 0:
        return "-"
    
    drawdown_pct = abs(drawdown) * 100  # Convert to positive percentage
    
    if drawdown_pct > 20:
        color = THEME["negative"]
    elif drawdown_pct > 10:
        color = THEME["warning"]
    else:
        color = THEME["neutral"]
    
    return color_span(f"-{drawdown_pct:.1f}%", color, bold=True)
