from market_updater.pricing import FxRates, build_price_variants


CONFIG = {
    "cardmarket_normal_price_priority": [
        "trendPrice",
        "averageSellPrice",
        "avg7",
        "lowPriceExPlus",
        "lowPrice",
    ],
    "cardmarket_reverse_price_priority": [
        "reverseHoloTrend",
        "reverseHoloSell",
        "reverseHoloAvg7",
        "reverseHoloLow",
    ],
    "tcgplayer_price_priority": ["market", "mid", "low"],
}


def sample_card():
    return {
        "id": "set1-1",
        "name": "Pikachu",
        "number": "001",
        "set": {"id": "set1", "name": "Example Set"},
        "cardmarket": {
            "url": "https://example/cardmarket",
            "updatedAt": "2026/08/04",
            "prices": {
                "trendPrice": 10.0,
                "reverseHoloTrend": 12.0,
            },
        },
        "tcgplayer": {
            "url": "https://example/tcgplayer",
            "updatedAt": "2026/08/04",
            "prices": {
                "normal": {"market": 20.0},
                "holofoil": {"market": 30.0},
                "reverseHolofoil": {"market": 40.0},
            },
        },
    }


def test_cardmarket_is_preferred_for_normal_and_reverse():
    prices = build_price_variants(
        sample_card(),
        FxRates(
            eur_to_gbp=0.85,
            usd_to_gbp=0.75,
            source="test",
            rate_date="2026-08-04",
        ),
        CONFIG,
    )
    by_variant = {price.variant: price for price in prices}

    assert by_variant["Normal"].price_gbp == 8.50
    assert "Cardmarket" in by_variant["Normal"].source
    assert by_variant["Reverse Holofoil"].price_gbp == 10.20
    assert "Cardmarket" in by_variant["Reverse Holofoil"].source
    assert by_variant["Holofoil"].price_gbp == 22.50
    assert "TCGplayer" in by_variant["Holofoil"].source
