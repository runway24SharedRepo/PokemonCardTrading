from datetime import datetime, timezone

from live_radar.core import Candidate, RadarResult
from live_radar.excel_adapter import ExcelAdapter


def test_live_result_has_40_columns():
    candidate = Candidate(
        card_id="base1-58",
        name="Pikachu",
        set_name="Base Set",
        number="58",
        variant="Normal",
        market_value=20,
        source="test",
        source_date="2026-08-04",
        source_url="https://example",
    )
    result = RadarResult(
        candidate=candidate,
        title="Pikachu Base Set 58/102",
        item_id="item",
        item_url="https://example/listing",
        listing_image_url="https://example/listing-image",
        current_bid=5,
        postage=1,
        delivered=6,
        market_value=20,
        ratio=0.3,
        target_delivered=15,
        maximum_bid=14,
        bid_headroom=9,
        decision="GREEN",
        recommended_action="WATCH / BID",
        score=90,
        end_time=datetime.now(timezone.utc),
        minutes_remaining=30,
        bid_count=1,
        seller="seller",
        feedback_percent=100,
        feedback_count=100,
        condition="Ungraded",
        condition_flag="AMBER",
        condition_details="Inspect photos",
        match_score=0.9,
        match_confidence="High",
        search_query="Pikachu Base Set 58",
        direct_search_url="https://example/search",
        sold_search_url="https://example/sold",
    )
    assert len(ExcelAdapter._result_row(1, result)) == 40
