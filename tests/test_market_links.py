from urllib.parse import parse_qs, urlparse

from market_links import (
    card_market_query,
    market_links_for_fields,
)


def query_from_url(url: str, parameter: str) -> str:
    return parse_qs(
        urlparse(url).query
    )[parameter][0]


def test_kyogre_ex_query_uses_name_and_id_only():
    assert card_market_query(
        "Kyogre-EX",
        "XY Black Star Promos",
        "XY41",
        "Holofoil",
    ) == "Kyogre EX XY41"


def test_set_and_variant_are_omitted():
    assert card_market_query(
        "Pikachu",
        "Base Set",
        "58/102",
        "Normal",
    ) == "Pikachu 58"


def test_apostrophes_and_special_characters_removed():
    assert card_market_query(
        "N's Zekrom",
        "Ascended Heroes",
        "155",
        "Reverse Holofoil",
    ) == "Ns Zekrom 155"

    assert card_market_query(
        "Farfetch'd",
        "Base Set 2",
        "40/130",
    ) == "Farfetchd 40"


def test_gender_symbols_are_searchable_words():
    assert card_market_query(
        "Nidoran♀",
        "Jungle",
        "57/64",
    ) == "Nidoran F 57"

    assert card_market_query(
        "Nidoran♂",
        "Jungle",
        "55/64",
    ) == "Nidoran M 55"


def test_alphanumeric_collector_numbers_are_preserved():
    assert card_market_query(
        "Garchomp C LV.X",
        "Diamond and Pearl Promos",
        "DP46",
    ) == "Garchomp C LV X DP46"

    assert card_market_query(
        "Pikachu",
        "Cosmic Eclipse",
        "TG06/TG30",
    ) == "Pikachu TG06"


def test_card_id_fallback_uses_final_token():
    assert card_market_query(
        "Kyogre-EX",
        "",
        "",
        "",
        "xy-p-xy41",
    ) == "Kyogre EX XY41"


def test_all_market_urls_use_same_compact_query():
    links = market_links_for_fields(
        "Kyogre-EX",
        "XY Black Star Promos",
        "XY41",
        "Promo",
    )

    assert query_from_url(
        links.uk_market,
        "q",
    ) == "Kyogre EX XY41"
    assert query_from_url(
        links.tcgplayer,
        "q",
    ) == "Kyogre EX XY41"
    assert query_from_url(
        links.cardmarket,
        "searchString",
    ) == "Kyogre EX XY41"
    assert query_from_url(
        links.pricecharting,
        "q",
    ) == "Kyogre EX XY41"


def test_all_urls_use_https():
    links = market_links_for_fields(
        "Charizard",
        "Base Set",
        "4/102",
        "Holofoil",
    )
    assert all(
        value.startswith("https://")
        for value in (
            links.uk_market,
            links.tcgplayer,
            links.cardmarket,
            links.pricecharting,
        )
    )
