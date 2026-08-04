from datetime import datetime, timezone
from types import SimpleNamespace

from random_sniper.excel_adapter import ExcelAdapter as RandomExcel
from live_radar.excel_adapter import ExcelAdapter as LiveExcel
from live_radar.core import Candidate as LiveCandidate, RadarResult


def test_random_result_row_has_links_at_columns_23_to_27():
    candidate = SimpleNamespace(
        name="Pikachu",
        set_name="Base Set",
        number="58",
        variant="Normal",
        card_id="base1-58",
        image_url="https://example/image",
    )
    result = SimpleNamespace(
        candidate=candidate,
        decision="GREEN",
        recommended_action="BID",
        score=90,
        listing_type="AUCTION",
        discovery_source="RANDOM SEARCH",
        parent_item_id="",
        title="Pikachu Base Set 58",
        item_id="item",
        current_bid=5,
        buy_now_price=None,
        postage=1,
        bid_delivered=6,
        buy_now_delivered=None,
        market_value=20,
        bid_ratio=0.3,
        buy_now_ratio=None,
        target_delivered=15,
        maximum_bid=14,
        bid_headroom=9,
        buy_now_headroom=None,
        bid_decision="GREEN",
        buy_now_decision="N/A",
        end_time=datetime.now(timezone.utc),
        minutes_remaining=20,
        bid_count=1,
        seller="seller",
        feedback_percent=100,
        feedback_count=100,
        condition="Ungraded",
        condition_flag="AMBER",
        condition_details="Inspect",
        match_confidence="High",
        search_query="Pikachu Base 58",
        item_url="https://example/listing",
        auction_search_url="https://example/auction",
        buy_now_search_url="https://example/buy",
        sold_search_url="https://example/sold",
        notes="",
    )
    row = RandomExcel._result_row(1, result)
    assert len(row) == 46
    assert row[22:27] == [
        "Open Listing",
        "Open Card Image",
        "Open Auction Search",
        "Open Buy Now Search",
        "Open Sold Results",
    ]


def test_live_result_row_has_links_at_columns_20_to_23():
    candidate = LiveCandidate(
        card_id="base1-58",
        name="Pikachu",
        set_name="Base Set",
        number="58",
        variant="Normal",
        market_value=20,
        source="test",
        source_date="2026-08-04",
        source_url="https://example",
        image_url="https://example/image",
    )
    result = RadarResult(
        candidate=candidate,
        title="Pikachu Base Set 58",
        item_id="item",
        item_url="https://example/listing",
        listing_image_url="",
        current_bid=5,
        postage=1,
        delivered=6,
        market_value=20,
        ratio=0.3,
        target_delivered=15,
        maximum_bid=14,
        bid_headroom=9,
        decision="GREEN",
        recommended_action="BID",
        score=90,
        end_time=datetime.now(timezone.utc),
        minutes_remaining=20,
        bid_count=1,
        seller="seller",
        feedback_percent=100,
        feedback_count=100,
        condition="Ungraded",
        condition_flag="AMBER",
        condition_details="Inspect",
        match_score=0.9,
        match_confidence="High",
        search_query="Pikachu Base 58",
        direct_search_url="https://example/search",
        sold_search_url="https://example/sold",
    )
    row = LiveExcel._result_row(1, result)
    assert len(row) == 40
    assert row[19:23] == [
        "Open Listing",
        "Open Card Image",
        "Open Auction Search",
        "Open Sold Results",
    ]
