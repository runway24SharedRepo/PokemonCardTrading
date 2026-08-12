from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_updater.pricing import FxRates, build_price_variants


def fx() -> FxRates:
    return FxRates(
        eur_to_gbp=0.86,
        usd_to_gbp=1.0 / 1.3479,
        source="Bank of England test fixture",
        rate_date="2026-08-05",
    )


def eevee_fixture() -> dict:
    return {
        "id": "base2-51",
        "name": "Eevee",
        "number": "51",
        "rarity": "Common",
        "set": {"id": "base2", "name": "Jungle"},
        "tcgplayer": {
            "url": "https://prices.pokemontcg.io/tcgplayer/base2-51",
            "updatedAt": "2026/08/05",
            "prices": {
                "1stEdition": {"market": 15.40},
                "unlimited": {
                    "low": 1.00,
                    "mid": 2.50,
                    "high": 99.00,
                    "market": 2.94,
                    "directLow": 1.25,
                },
            },
        },
        "cardmarket": {"prices": {"trendPrice": 1234.56}},
    }


def test_eevee_unlimited_exact_market() -> None:
    rows = build_price_variants(eevee_fixture(), fx(), {})
    unlimited = next(row for row in rows if row.edition == "Unlimited")
    first = next(row for row in rows if row.edition == "1st Edition")

    assert unlimited.card_id == "base2-51"
    assert unlimited.finish == "Normal"
    assert unlimited.selected_price_category == "unlimited"
    assert unlimited.source_field == "tcgplayer.prices.unlimited.market"
    assert unlimited.original_price == 2.94
    assert unlimited.exchange_rate_usd_per_gbp == 1.3479
    assert unlimited.price_gbp == 2.18
    assert unlimited.match_status == "EXACT TCGPLAYER MARKET"

    assert first.original_price == 15.40
    assert first.price_gbp != unlimited.price_gbp


def test_only_market_is_accepted() -> None:
    card = eevee_fixture()
    card["tcgplayer"]["prices"] = {
        "normal": {"low": 1.00, "mid": 3.00, "high": 20.00}
    }
    row = build_price_variants(card, fx(), {})[0]
    assert row.price_gbp is None
    assert row.match_status == "PRICE UNAVAILABLE"


def test_finish_and_edition_are_never_mixed() -> None:
    card = eevee_fixture()
    card["tcgplayer"]["prices"] = {
        "normal": {"market": 2.00},
        "holofoil": {"market": 5.00},
        "reverseHolofoil": {"market": 7.00},
        "1stEditionNormal": {"market": 11.00},
        "1stEditionHolofoil": {"market": 19.00},
    }
    rows = build_price_variants(card, fx(), {})
    identities = {
        row.selected_price_category: (row.finish, row.edition)
        for row in rows
    }
    assert identities == {
        "normal": ("Normal", "Unlimited"),
        "holofoil": ("Holofoil", "Unlimited"),
        "reverseHolofoil": ("Reverse Holofoil", "Unlimited"),
        "1stEditionNormal": ("Normal", "1st Edition"),
        "1stEditionHolofoil": ("Holofoil", "1st Edition"),
    }


def test_ambiguous_generic_vintage_holo_is_not_guessed() -> None:
    card = eevee_fixture()
    card["rarity"] = "Rare Holo"
    card["tcgplayer"]["prices"] = {"unlimited": {"market": 50.00}}
    row = build_price_variants(card, fx(), {})[0]
    assert row.price_gbp is None
    assert row.match_status == "PRICE UNAVAILABLE - AMBIGUOUS VARIANT"


def test_duplicate_alias_never_creates_two_buyable_rows() -> None:
    card = eevee_fixture()
    card["tcgplayer"]["prices"] = {
        "normal": {"market": 2.94},
        "unlimited": {"market": 9.99},
    }
    rows = build_price_variants(card, fx(), {})
    enabled = [row for row in rows if row.has_market_price]
    disabled = [row for row in rows if not row.has_market_price]
    assert len(enabled) == 1
    assert enabled[0].selected_price_category == "normal"
    assert disabled[0].match_status == "PRICE UNAVAILABLE - DUPLICATE CATEGORY"


def test_project_contains_no_ai_pricing_path() -> None:
    checked = [
        ROOT / "update_pokemon_market.py",
        ROOT / "market_updater" / "pricing.py",
        ROOT / "market_updater" / "excel_writer.py",
    ]
    content = "\n".join(path.read_text(encoding="utf-8") for path in checked)
    assert "openai" not in content.casefold()
    assert "ai_market_pricer" not in content.casefold()


def test_configuration_is_strict() -> None:
    config = json.loads((ROOT / "market-updater-config.json").read_text())
    assert config["pricing_policy"] == "exact_tcgplayer_market_only"
    assert "tcgplayer_price_priority" not in config
    assert "cardmarket_normal_price_priority" not in config


def test_market_import_keeps_scanner_columns_and_audit_fields() -> None:
    path = ROOT / "market_updater" / "excel_writer.py"
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
        "Estimated Current Selling Value (£)",
        "Source",
        "Source Date",
        "Source URL",
        "Notes",
    ]
    assert headers[12:] == [
        "Card ID",
        "Set Code",
        "Finish",
        "Edition",
        "Selected TCGplayer Price Category",
        "TCGplayer Market USD",
        "USD per GBP",
        "Base Imported Value (£)",
        "Base Imported Source",
        "Override Value (£)",
        "Override Source",
        "Match Status",
        "Available TCGplayer Variants / Prices",
        "Last Synced",
    ]
    assert len(headers) == len(widths) == 26


def test_workbook_write_is_staged_before_replace() -> None:
    source = (ROOT / "market_updater" / "excel_writer.py").read_text(
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
    eevee = next(
        row
        for row in build_price_variants(eevee_fixture(), fx(), {})
        if row.edition == "Unlimited"
    )
    print()
    print("EEVEE ACCEPTANCE RESULT")
    print(f"Card ID: {eevee.card_id}")
    print(f"Variant: {eevee.finish} / {eevee.edition}")
    print(f"Selected JSON field: {eevee.source_field}")
    print(f"Market USD: {eevee.original_price:.2f}")
    print(f"Exchange rate: 1 GBP = {eevee.exchange_rate_usd_per_gbp:.4f} USD")
    print(f"Converted GBP: {eevee.price_gbp:.2f}")
    print(f"Status: {eevee.match_status}")
    print(f"PASS: {len(tests)} Phase 5.6.5 tests")
