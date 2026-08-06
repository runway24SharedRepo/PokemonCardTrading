from edition_safety import (
    edition_conflict,
    safe_reference_image_url,
)
from market_updater.pricing import (
    FxRates,
    build_price_variants,
)
from random_sniper.core import (
    Candidate,
    _dedupe_cards,
    listing_match_score,
)
from random_sniper.seller_discovery import (
    CandidateTitleMatcher,
)


def card(variant, value):
    return Candidate(
        card_id="base1-53",
        name="Magnemite",
        set_name="Base",
        number="53",
        variant=variant,
        market_value=value,
        source="test",
        source_date="2026-08-06",
        source_url="https://example",
        supertype="Pokémon",
    )


title = (
    "Pokémon Magnemite 53/102 Base Set WOTC "
    "1999 Unlimited Common TCG Card"
)
normal = card("Normal", 2.0)
first = card("1st Edition Normal", 25.0)

normal_score, normal_reason = listing_match_score(
    normal,
    title,
    [],
)
first_score, first_reason = listing_match_score(
    first,
    title,
    [],
)

assert normal_score > 0.72, normal_reason
assert first_score == 0
assert "Unlimited" in first_reason
assert CandidateTitleMatcher(
    [first, normal]
).match(title, []) is normal

generic_title = (
    "Pokemon Magnemite Base Set 53/102 "
    "Common 1999 NM"
)
assert edition_conflict(
    "1st Edition Normal",
    generic_title,
)
assert not edition_conflict(
    "Normal",
    generic_title,
)
assert _dedupe_cards(
    [first, normal],
    True,
) == [normal]

source_card = {
    "id": "base1-53",
    "name": "Magnemite",
    "number": "53",
    "set": {
        "id": "base1",
        "name": "Base",
    },
    "cardmarket": {
        "url": "https://example/cardmarket",
        "updatedAt": "2026/08/06",
        "prices": {
            "trendPrice": 40.0,
        },
    },
    "tcgplayer": {
        "url": "https://example/tcgplayer",
        "updatedAt": "2026/08/06",
        "prices": {
            "normal": {"market": 2.0},
            "1stEditionNormal": {
                "market": 30.0,
            },
        },
    },
}
config = {
    "cardmarket_normal_price_priority": [
        "trendPrice",
    ],
    "cardmarket_reverse_price_priority": [
        "reverseHoloTrend",
    ],
    "tcgplayer_price_priority": [
        "market",
    ],
}
prices = build_price_variants(
    source_card,
    FxRates(
        eur_to_gbp=0.85,
        usd_to_gbp=0.75,
        source="test",
        rate_date="2026-08-06",
    ),
    config,
)
by_variant = {
    item.variant: item
    for item in prices
}
assert by_variant["Normal"].price_gbp == 1.50
assert (
    by_variant["1st Edition Normal"].price_gbp
    == 22.50
)
assert "edition-specific" in (
    by_variant["Normal"].source
)
assert safe_reference_image_url(
    "https://example/generic",
    30.0,
    None,
) == ""

print("Edition-safe verification passed.")
print("Unlimited Magnemite uses the Normal price.")
print("First Edition requires explicit title evidence.")
print("Edition-ambiguous reference images are suppressed.")
