from datetime import datetime, timezone

from random_sniper.core import Candidate, ListingResult
from random_sniper.seller_discovery import (
    CandidateTitleMatcher,
    group_queue_results,
)


def candidate(name, number, card_id):
    return Candidate(
        card_id=card_id,
        name=name,
        set_name="Example Set",
        number=number,
        variant="Holofoil",
        market_value=20,
        source="test",
        source_date="2026-08-04",
        source_url="https://example",
        supertype="Pokémon",
    )


def test_matcher_requires_name_and_number():
    pikachu = candidate("Pikachu", "54", "set-54")
    matcher = CandidateTitleMatcher([pikachu])
    assert matcher.match(
        "Pokemon Pikachu 54/100 Holo Card",
        [],
    ) is pikachu
    assert matcher.match(
        "Pokemon Pikachu Holo Card",
        [],
    ) is None


def result(item_id, seller, source, decision="GREEN"):
    card = candidate("Pikachu", "54", "set-54")
    return ListingResult(
        candidate=card,
        title="Pikachu 54",
        item_id=item_id,
        item_url="https://example",
        image_url="",
        buying_options=("FIXED_PRICE",),
        listing_type="BUY IT NOW",
        current_bid=None,
        buy_now_price=10,
        postage=1,
        bid_delivered=None,
        buy_now_delivered=11,
        market_value=20,
        bid_ratio=None,
        buy_now_ratio=0.55,
        target_delivered=15,
        maximum_bid=None,
        bid_headroom=None,
        buy_now_headroom=4,
        bid_decision="N/A",
        buy_now_decision=decision,
        recommended_action="BUY NOW",
        end_time=datetime.now(timezone.utc),
        minutes_remaining=100,
        within_sniping_window=False,
        queue_eligible=True,
        bid_count=0,
        seller=seller,
        feedback_percent=100,
        feedback_count=100,
        condition="Ungraded",
        match_score=0.9,
        match_confidence="High",
        search_query="Pikachu 54",
        auction_search_url="https://example",
        buy_now_search_url="https://example",
        sold_search_url="https://example",
        score=90,
        decision=decision,
        discovery_source=source,
    )


def test_seller_rows_follow_green_anchor():
    anchor = result("anchor", "seller1", "RANDOM SEARCH")
    other = result("other", "seller1", "↳ SAME SELLER")
    unrelated = result("unrelated", "seller2", "RANDOM SEARCH", "AMBER")
    grouped = group_queue_results([anchor, unrelated], [other])
    assert [item.item_id for item in grouped] == [
        "anchor",
        "other",
        "unrelated",
    ]
