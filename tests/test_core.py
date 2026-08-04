from datetime import datetime, timezone

from random_sniper.core import (
    Candidate,
    Settings,
    build_queries,
    ebay_active_search_url,
    ebay_sold_search_url,
    eligible_candidates,
    listing_match_score,
    normalize_card_number,
    select_candidates,
)


def card(value, name="Pikachu", number="58", variant="Normal"):
    return Candidate(
        card_id=f"id-{value}",
        name=name,
        set_name="Base",
        number=number,
        variant=variant,
        market_value=float(value),
        source="test",
        source_date="2026-08-04",
        source_url="https://example",
        supertype="Pokémon",
        release_date="1999-01-09",
    )


def test_query_and_links():
    candidate = card(10)
    queries = build_queries(candidate, "Balanced")
    assert len(queries) == 2
    assert "Pikachu" in queries[0]
    assert "58" in queries[0]
    assert "LH_Auction=1" in ebay_active_search_url(queries[0])
    assert "LH_Sold=1" in ebay_sold_search_url(queries[0])


def test_matching_exact_card():
    candidate = card(10)
    score, reason = listing_match_score(
        candidate,
        "Pikachu Base Set 58/102 Pokemon Card Near Mint",
        ["PSA", "proxy"],
    )
    assert reason == ""
    assert score >= 0.70


def test_excluded_listing():
    candidate = card(10)
    score, reason = listing_match_score(
        candidate,
        "PSA 9 Pikachu Base Set 58/102",
        ["PSA", "proxy"],
    )
    assert score == 0
    assert "Excluded" in reason


def test_smart_random_range():
    settings = Settings(
        minimum_value=5,
        maximum_value=50,
        number_of_cards=5,
        random_seed="test",
    )
    values = [card(value) for value in range(5, 51)]
    eligible = eligible_candidates(
        values,
        settings,
        datetime.now(timezone.utc),
        2010,
        2020,
    )
    selected = select_candidates(eligible, settings)
    assert len(selected) == 5
    assert all(5 <= item.market_value <= 50 for item in selected)


def test_excel_whole_number_card_number_is_cleaned():
    assert normalize_card_number(54.0) == "54"
    assert normalize_card_number(54) == "54"
    assert normalize_card_number("54.0") == "54"
    assert normalize_card_number("054") == "054"
    assert normalize_card_number("RC10") == "RC10"
    assert normalize_card_number("58/102") == "58/102"
