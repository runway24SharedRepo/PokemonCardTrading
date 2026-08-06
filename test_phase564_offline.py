from __future__ import annotations

import tempfile
from pathlib import Path

from disable_ai_integration import remove_openai_settings
from market_updater.pricing import FxRates, build_price_variants


ROOT = Path(__file__).resolve().parent


def test_no_ai_calls_in_automatic_paths() -> None:
    files = [
        "live_opportunity_radar.py",
        "random_range_sniper.py",
        "seller_radar.py",
        "update_pokemon_market.py",
    ]
    forbidden = (
        "from openai import",
        "import openai",
        "AIListingMarketPricer",
        "reprice_candidate(",
        "restore_ai_market_prices",
    )
    for name in files:
        source = (ROOT / name).read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"{marker!r} remains in {name}"

    writer = (ROOT / "market_updater" / "excel_writer.py").read_text(
        encoding="utf-8"
    )
    assert "market.Cells(old_last, 28)" in writer


def test_tcgplayer_market_is_primary() -> None:
    card = {
        "id": "base1-58",
        "name": "Pikachu",
        "number": "58",
        "set": {"name": "Base"},
        "tcgplayer": {
            "url": "https://example.invalid/tcg",
            "updatedAt": "2026-08-06",
            "prices": {
                "normal": {
                    "market": 10.0,
                    "mid": 11.0,
                }
            },
        },
        "cardmarket": {
            "url": "https://example.invalid/cm",
            "updatedAt": "2026-08-06",
            "prices": {
                "trendPrice": 99.0,
            },
        },
    }
    config = {
        "tcgplayer_price_priority": ["market", "mid", "low", "high"],
        "cardmarket_normal_price_priority": ["trendPrice"],
        "cardmarket_reverse_price_priority": ["reverseHoloTrend"],
    }
    values = build_price_variants(
        card,
        FxRates(
            usd_to_gbp=0.8,
            eur_to_gbp=0.9,
            source="offline test",
            rate_date="2026-08-06",
        ),
        config,
    )
    normal = next(value for value in values if value.variant == "Normal")
    assert normal.price_gbp == 8.0
    assert "TCGplayer" in normal.source


def test_openai_settings_are_removed_only() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        env = root / ".env"
        backup = root / "backup"
        backup.mkdir()
        env.write_text(
            "EBAY_CLIENT_ID=keep\n"
            "POKEMON_TCG_API_KEY=keep-too\n"
            "OPENAI_API_KEY=remove\n"
            "AI_MARKET_MODEL=remove\n",
            encoding="utf-8",
        )
        removed = remove_openai_settings(env, backup)
        result = env.read_text(encoding="utf-8")
        assert removed == 2
        assert "EBAY_CLIENT_ID=keep" in result
        assert "POKEMON_TCG_API_KEY=keep-too" in result
        assert "OPENAI" not in result
        assert "AI_MARKET" not in result


def main() -> int:
    test_no_ai_calls_in_automatic_paths()
    test_tcgplayer_market_is_primary()
    test_openai_settings_are_removed_only()
    print("PHASE 5.6.4 OFFLINE TESTS PASSED")
    print("TCGplayer market is primary.")
    print("No OpenAI call exists in Live, Random, Seller or market update paths.")
    print("No eBay, Pokemon TCG or OpenAI network request was made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
