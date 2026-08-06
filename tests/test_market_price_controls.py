from market_price_controls import (
    MarketPriceControl,
    resolve_effective_value,
)
from market_updater.pricing import (
    PriceVariant,
)


def price():
    return PriceVariant(
        card_id="base1-58",
        card_name="Pikachu",
        set_id="base1",
        set_name="Base",
        card_number="58",
        variant="Normal",
        price_gbp=5.70,
        source=(
            "Pokémon TCG API / TCGplayer "
            "(primary market)"
        ),
        source_date="2026/08/06",
        source_url="https://example",
        original_price=7.59,
        original_currency="USD",
        source_field="market",
    )


def test_no_override_keeps_imported_value():
    result = resolve_effective_value(
        price(),
        {},
    )
    assert result.effective_value_gbp == 5.70
    assert (
        result.price_status
        == "TCGPLAYER PRIMARY"
    )


def test_pricecharting_override_becomes_authoritative():
    control = MarketPriceControl(
        card_id="base1-58",
        variant="Normal",
        override_value_gbp=3.00,
        override_source="PriceCharting",
        source_url=(
            "https://www.pricecharting.com/"
            "game/pokemon-base-set/pikachu-58"
        ),
        source_date="2026-08-06",
    )
    result = resolve_effective_value(
        price(),
        {control.key: control},
    )

    assert result.effective_value_gbp == 3.00
    assert (
        result.price_status
        == "PRICECHARTING OVERRIDE"
    )
    assert result.base_value_gbp == 5.70
