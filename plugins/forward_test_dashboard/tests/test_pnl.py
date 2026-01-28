from pnl import build_pnl_map


def test_build_pnl_map_basic():
    positions = [
        {
            "symbol": "BTC",
            "modelKey": "model-1",
            "entryTime": "2026-01-01T09:12:45Z",
            "pnl": 1.234,
        }
    ]

    pnl_map = build_pnl_map(positions)

    assert len(pnl_map) == 1
    key = ("BTC", "model-1", "2026-01-01T09:00:00")
    assert pnl_map[key] == 1.234


def test_build_pnl_map_multiple_hours():
    positions = [
        {
            "symbol": "ETH",
            "modelKey": "model-2",
            "entryTime": "2026-01-01T10:59:59Z",
            "pnl": -0.5,
        },
        {
            "symbol": "ETH",
            "modelKey": "model-2",
            "entryTime": "2026-01-01T11:00:01Z",
            "pnl": 0.25,
        },
    ]

    pnl_map = build_pnl_map(positions)

    assert len(pnl_map) == 2
    assert pnl_map[("ETH", "model-2", "2026-01-01T10:00:00")] == -0.5
    assert pnl_map[("ETH", "model-2", "2026-01-01T11:00:00")] == 0.25


def test_build_pnl_map_duplicate_overwrites():
    positions = [
        {
            "symbol": "SOL",
            "modelKey": "model-3",
            "entryTime": "2026-01-01T12:10:00Z",
            "pnl": 0.1,
        },
        {
            "symbol": "SOL",
            "modelKey": "model-3",
            "entryTime": "2026-01-01T12:59:59Z",
            "pnl": 0.9,
        },
    ]

    pnl_map = build_pnl_map(positions)

    # Last write wins (same hour)
    assert pnl_map[("SOL", "model-3", "2026-01-01T12:00:00")] == 0.9


def test_build_pnl_map_empty():
    pnl_map = build_pnl_map([])
    assert pnl_map == {}
