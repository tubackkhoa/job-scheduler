from parsing import parse_table_message


def test_parse_table():
    msg = """
    ranking table ::::
    pred_time base_asset new_mu
    2026-01-01 BTC 0.12
    """
    parsed = parse_table_message(msg)
    assert parsed
    assert parsed["header"] == ["pred_time", "base_asset", "new_mu"]
    assert parsed["rows"][0][1] == "BTC"
