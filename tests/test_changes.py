from market_updater.pricing import PriceVariant
from update_pokemon_market import build_changes


def price(value):
    return PriceVariant(
        card_id="set1-1",
        card_name="Pikachu",
        set_id="set1",
        set_name="Example",
        card_number="001",
        variant="Normal",
        price_gbp=value,
        source="Test",
        source_date="2026/08/04",
        source_url="https://example",
        original_price=value,
        original_currency="GBP",
        source_field="market",
    )


def test_changes_ignore_new_baseline():
    assert build_changes([price(10.0)], {}, 0.01, "now") == []


def test_changes_detect_price_move():
    changes = build_changes(
        [price(11.0)],
        {("set1-1", "Normal"): 10.0},
        0.01,
        "now",
    )
    assert len(changes) == 1
    assert changes[0]["change_gbp"] == 1.0
    assert changes[0]["change_percent"] == 0.1
