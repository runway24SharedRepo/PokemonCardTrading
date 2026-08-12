from __future__ import annotations

import ast
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload"
sys.path.insert(0, str(PAYLOAD))

from market_updater.database import MarketDatabase
from market_updater.pricing import FxRates, build_price_variants


def fx() -> FxRates:
    return FxRates(
        eur_to_gbp=0.86,
        usd_to_gbp=1.0 / 1.3479,
        source="Test reference rate",
        rate_date="2026-08-06",
    )


def palkia_fixture() -> dict:
    return {
        "id": "dp5-11",
        "name": "Palkia",
        "number": "11",
        "rarity": "Rare Holo",
        "set": {"id": "dp5", "name": "Majestic Dawn"},
        "tcgplayer": {
            "prices": {
                "holofoil": {"market": 65.92},
                "reverseHolofoil": {"market": 26.67},
            }
        },
        "cardmarket": {
            "url": "https://prices.pokemontcg.io/cardmarket/dp5-11",
            "updatedAt": "2026/08/05",
            "prices": {
                "averageSellPrice": 15.03,
                "reverseHoloSell": 12.00,
                "trendPrice": 15.19,
                "avg7": 14.50,
                "avg30": 14.10,
            },
        },
    }


def eevee_fixture() -> dict:
    return {
        "id": "base2-51",
        "name": "Eevee",
        "number": "51",
        "rarity": "Common",
        "set": {"id": "base2", "name": "Jungle"},
        "tcgplayer": {
            "prices": {
                "1stEdition": {"market": 15.40},
                "unlimited": {"market": 2.94},
            }
        },
        "cardmarket": {
            "url": "https://prices.pokemontcg.io/cardmarket/base2-51",
            "updatedAt": "2026/08/05",
            "prices": {
                "averageSellPrice": 2.50,
                "trendPrice": 99.99,
            },
        },
    }


def test_palkia_holo_uses_average_sell() -> None:
    rows = build_price_variants(palkia_fixture(), fx(), {})
    holo = next(row for row in rows if row.variant == "Holofoil")
    reverse = next(row for row in rows if row.variant == "Reverse Holofoil")

    assert holo.card_id == "dp5-11"
    assert holo.source_field == "cardmarket.prices.averageSellPrice"
    assert holo.original_price == 15.03
    assert holo.original_currency == "EUR"
    assert holo.exchange_rate_to_gbp == 0.86
    assert holo.price_gbp == 12.93
    assert holo.match_status == "EXACT CARDMARKET AVERAGE SELL"

    assert reverse.source_field == "cardmarket.prices.reverseHoloSell"
    assert reverse.original_price == 12.00
    assert reverse.price_gbp == 10.32


def test_tcgplayer_market_and_trend_are_never_used() -> None:
    card = palkia_fixture()
    card["cardmarket"]["prices"].pop("averageSellPrice")
    row = next(
        value
        for value in build_price_variants(card, fx(), {})
        if value.variant == "Holofoil"
    )
    assert row.price_gbp is None
    assert row.original_price is None
    assert row.source_field == "cardmarket.prices.averageSellPrice"
    assert "no substitute" in row.notes


def test_first_edition_is_not_given_unlimited_average() -> None:
    rows = build_price_variants(eevee_fixture(), fx(), {})
    unlimited = next(row for row in rows if row.edition == "Unlimited")
    first = next(row for row in rows if row.edition == "1st Edition")

    assert unlimited.variant == "Normal"
    assert unlimited.price_gbp == 2.15
    assert unlimited.source_field == "cardmarket.prices.averageSellPrice"
    assert first.price_gbp is None
    assert first.match_status == "PRICE UNAVAILABLE - EDITION NOT SEPARATED"


def test_no_cardmarket_average_means_unavailable() -> None:
    card = eevee_fixture()
    card["cardmarket"]["prices"] = {
        "trendPrice": 20.00,
        "avg7": 18.00,
        "avg30": 17.00,
    }
    unlimited = next(
        row
        for row in build_price_variants(card, fx(), {})
        if row.edition == "Unlimited"
    )
    assert unlimited.price_gbp is None
    assert unlimited.match_status == "PRICE UNAVAILABLE"


def test_project_contains_no_ai_pricing_path() -> None:
    checked = [
        PAYLOAD / "update_pokemon_market.py",
        PAYLOAD / "market_updater" / "pricing.py",
        PAYLOAD / "market_updater" / "excel_writer.py",
    ]
    content = "\n".join(path.read_text(encoding="utf-8") for path in checked)
    assert "openai" not in content.casefold()
    assert "ai_market_pricer" not in content.casefold()


def test_configuration_selects_average_selling_price() -> None:
    config = json.loads((PAYLOAD / "market-updater-config.json").read_text())
    assert config["pricing_policy"] == "cardmarket_average_selling_price_only"


def test_market_import_keeps_column_h_contract() -> None:
    path = PAYLOAD / "market_updater" / "excel_writer.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    headers = None
    widths = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id == "market_headers":
            headers = ast.literal_eval(node.value)
        if target.id == "widths":
            widths = ast.literal_eval(node.value)
    assert headers is not None
    assert headers[:12] == [
        "Enabled",
        "Card Name",
        "Set Name",
        "Card Number",
        "Variant",
        "Language",
        "Condition",
        "Average Selling Price (£)",
        "Source",
        "Source Date",
        "Source URL",
        "Notes",
    ]
    assert headers[16:20] == [
        "Variant Identity Source",
        "Cardmarket Average Sell EUR",
        "EUR to GBP",
        "Base Average Selling Price (£)",
    ]
    assert len(headers) == len(widths) == 26


def test_old_metric_is_excluded_from_new_baseline() -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "test.sqlite"
        database = MarketDatabase(path)
        database.connection.execute(
            "INSERT INTO current_prices(card_id, variant, card_name, price_gbp, "
            "source, last_synced, price_metric) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("dp5-11", "Holofoil", "Palkia", 48.95, "old", "now", "legacy"),
        )
        database.connection.commit()
        assert database.current_price_map("cardmarket_average_selling_price_only") == {}
        database.close()


def test_database_commit_stores_new_metric() -> None:
    with tempfile.TemporaryDirectory() as folder:
        database = MarketDatabase(Path(folder) / "test.sqlite")
        run_id = database.start_run()
        price = next(
            row
            for row in build_price_variants(palkia_fixture(), fx(), {})
            if row.variant == "Holofoil"
        )
        metric = "cardmarket_average_selling_price_only"
        database.commit_sync(
            run_id=run_id,
            cards=[palkia_fixture()],
            prices=[price],
            fx=fx(),
            changed_prices=[],
            price_metric=metric,
        )
        assert database.current_price_map(metric) == {
            ("dp5-11", "Holofoil"): 12.93
        }
        database.close()


def test_workbook_write_is_staged_before_replace() -> None:
    source = (PAYLOAD / "market_updater" / "excel_writer.py").read_text(
        encoding="utf-8"
    )
    assert ".market-update-staging" in source
    assert "staging_path.replace(workbook_path)" in source


if __name__ == "__main__":
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    palkia = next(
        row
        for row in build_price_variants(palkia_fixture(), fx(), {})
        if row.variant == "Holofoil"
    )
    print()
    print("PALKIA ACCEPTANCE RESULT")
    print(f"Card ID: {palkia.card_id}")
    print(f"Variant: {palkia.finish} / {palkia.edition}")
    print(f"Selected JSON field: {palkia.source_field}")
    print(f"Average Sell EUR: {palkia.original_price:.2f}")
    print(f"EUR to GBP: {palkia.exchange_rate_to_gbp:.4f}")
    print(f"Converted GBP: {palkia.price_gbp:.2f}")
    print(f"Status: {palkia.match_status}")
    print(f"PASS: {len(tests)} Phase 5.6.6 tests")
