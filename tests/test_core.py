from datetime import datetime, timezone

from live_radar.core import (
    Candidate,
    CandidateTitleMatcher,
    RadarSettings,
    card_number_match,
    decision_for,
    ebay_direct_search_url,
    ebay_sold_search_url,
    normalize_card_number,
    score_listing,
    within_time_window,
)


def card(
    name="Pikachu",
    number="58",
    set_name="Base Set",
    market=20.0,
):
    return Candidate(
        card_id=f"{set_name}-{number}",
        name=name,
        set_name=set_name,
        number=number,
        variant="Normal",
        market_value=market,
        source="test",
        source_date="2026-08-04",
        source_url="https://example",
    )


def test_excel_number_cleanup():
    assert normalize_card_number(54.0) == "54"
    assert normalize_card_number("54.0") == "54"
    assert normalize_card_number("RC10") == "RC10"
    assert normalize_card_number("58/102") == "58/102"


def test_title_match_requires_exact_number():
    matcher = CandidateTitleMatcher([card()])
    matched, score, reason = matcher.match(
        "Pokemon Pikachu Base Set 58/102 Card",
        [],
    )
    assert matched is not None
    assert score >= 0.72
    assert reason == ""

    matched, _, _ = matcher.match(
        "Pokemon Pikachu Base Set Card",
        [],
    )
    assert matched is None


def test_time_window():
    settings = RadarSettings(
        minimum_minutes_remaining=2,
        maximum_hours_remaining=24,
    )
    assert within_time_window(2, settings)
    assert within_time_window(1440, settings)
    assert not within_time_window(1, settings)
    assert not within_time_window(1441, settings)


def test_green_decision():
    settings = RadarSettings(
        target_ratio=0.75,
        amber_upper_ratio=0.90,
        minimum_feedback=98,
        minimum_feedback_count=25,
    )
    assert decision_for(
        ratio=0.70,
        match_score=0.90,
        feedback_percent=99.5,
        feedback_count=100,
        settings=settings,
        headroom=2.0,
    ) == "GREEN"


def test_links():
    assert "LH_Auction=1" in ebay_direct_search_url(
        "Pikachu Base 58"
    )
    assert "LH_Sold=1" in ebay_sold_search_url(
        "Pikachu Base 58"
    )


def test_last_minute_score_has_urgency():
    urgent = score_listing(
        0.70,
        0.90,
        99.0,
        3,
        1,
        0.75,
    )
    later = score_listing(
        0.70,
        0.90,
        99.0,
        600,
        1,
        0.75,
    )
    assert urgent > later
