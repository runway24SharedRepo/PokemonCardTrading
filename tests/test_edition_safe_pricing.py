from edition_safety import (
    edition_conflict,
    preferred_result_image,
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


UNLIMITED = (
    "Pokémon Magnemite 53/102 Base Set WOTC "
    "1999 Unlimited Common TCG Card"
)


def test_unlimited_selects_normal_not_first_edition():
    normal = card("Normal", 2)
    first = card("1st Edition Normal", 25)
    assert CandidateTitleMatcher(
        [first, normal]
    ).match(UNLIMITED, []) is normal


def test_first_edition_requires_explicit_wording():
    first = card("1st Edition Normal", 25)
    score, reason = listing_match_score(
        first,
        "Pokemon Magnemite Base Set 53/102 Common NM",
        [],
    )
    assert score == 0
    assert "requires explicit" in reason


def test_explicit_first_edition_selects_first():
    normal = card("Normal", 2)
    first = card("1st Edition Normal", 25)
    title = (
        "Pokemon Magnemite Base Set 53/102 "
        "1st Edition Common NM"
    )
    assert CandidateTitleMatcher(
        [normal, first]
    ).match(title, []) is first


def test_unlimited_hard_rejects_first_edition():
    assert "Unlimited" in edition_conflict(
        "1st Edition Normal",
        UNLIMITED,
    )


def test_dedupe_prefers_standard_over_first():
    normal = card("Normal", 2)
    first = card("1st Edition Normal", 25)
    assert _dedupe_cards(
        [first, normal],
        True,
    ) == [normal]


def test_market_updater_uses_tcg_standard_value():
    source = {
        "id": "base1-53",
        "name": "Magnemite",
        "number": "53",
        "set": {
            "id": "base1",
            "name": "Base",
        },
        "cardmarket": {
            "prices": {
                "trendPrice": 40.0,
            },
        },
        "tcgplayer": {
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
        source,
        FxRates(
            eur_to_gbp=0.85,
            usd_to_gbp=0.75,
            source="test",
            rate_date="2026-08-06",
        ),
        config,
    )
    values = {
        item.variant: item
        for item in prices
    }
    assert values["Normal"].price_gbp == 1.50
    assert (
        values["1st Edition Normal"].price_gbp
        == 22.50
    )


def test_unsafe_standard_value_is_omitted():
    source = {
        "id": "base1-53",
        "name": "Magnemite",
        "number": "53",
        "set": {
            "id": "base1",
            "name": "Base",
        },
        "cardmarket": {
            "prices": {
                "trendPrice": 40.0,
            },
        },
        "tcgplayer": {
            "prices": {
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
    variants = {
        item.variant
        for item in build_price_variants(
            source,
            FxRates(
                eur_to_gbp=0.85,
                usd_to_gbp=0.75,
                source="test",
                rate_date="2026-08-06",
            ),
            config,
        )
    }
    assert "Normal" not in variants
    assert "1st Edition Normal" in variants


def test_generic_edition_image_is_hidden():
    assert safe_reference_image_url(
        "https://example/reference",
        30,
        None,
    ) == ""


def test_listing_photo_is_preferred():
    assert preferred_result_image(
        "https://ebay/photo",
        "https://database/reference",
    ) == "https://ebay/photo"
