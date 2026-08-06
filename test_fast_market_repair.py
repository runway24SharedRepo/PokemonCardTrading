from datetime import datetime

from market_price_controls import (
    MarketPriceControl,
)
from repair_market_value_authority import (
    repair_market_matrix,
)


def details():
    return {
        (
            "pikachu",
            "base",
            "58",
        ): {
            "card_id": "base1-58",
            "normal": 4.0,
            "holo": None,
            "reverse": None,
            "first_normal": 20.0,
            "first_holo": None,
            "cm_normal": 14.0,
            "cm_reverse": None,
            "source_date": "2026-08-06",
            "source_url": "https://example",
        }
    }


def market_row():
    return [
        "YES",
        "Pikachu",
        "Base",
        "58",
        "Normal",
        "English",
        "Market reference",
        12.38,
        "Old source",
        "",
        "",
        "",
    ]


def test_bulk_repair_prefers_tcgplayer_normal():
    rows, stats = repair_market_matrix(
        [market_row()],
        details(),
        {},
        eur_to_gbp=0.85,
        usd_to_gbp=0.75,
        now=datetime(2026, 8, 6),
    )

    assert rows[0][7] == 3.00
    assert "TCGplayer" in rows[0][8]
    assert rows[0][12] == "base1-58"
    assert rows[0][13] == 3.00
    assert rows[0][17] == "TCGPLAYER PRIMARY"
    assert stats["corrected"] == 1


def test_bulk_repair_applies_verified_override():
    control = MarketPriceControl(
        card_id="base1-58",
        variant="Normal",
        override_value_gbp=2.90,
        override_source="PriceCharting",
        source_url="https://pricecharting/example",
        source_date="2026-08-06",
    )
    rows, stats = repair_market_matrix(
        [market_row()],
        details(),
        {control.key: control},
        eur_to_gbp=0.85,
        usd_to_gbp=0.75,
        now=datetime(2026, 8, 6),
    )

    assert rows[0][7] == 2.90
    assert rows[0][15] == 2.90
    assert rows[0][17] == "PRICECHARTING OVERRIDE"
    assert stats["overrides"] == 1
