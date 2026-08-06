from pathlib import Path


def test_random_and_live_read_market_data_column_h():
    root = Path(__file__).resolve().parents[1]

    random_code = (
        root
        / "random_sniper"
        / "excel_adapter.py"
    ).read_text(encoding="utf-8")
    live_code = (
        root
        / "live_radar"
        / "excel_adapter.py"
    ).read_text(encoding="utf-8")

    assert 'sheet("Market Data Import")' in random_code
    assert 'row[7]' in random_code
    assert 'sheet("Market Data Import")' in live_code
    assert 'row[7]' in live_code
