from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from seller_radar import (
    displayed_price,
    listing_type,
    safe_limit,
)
from seller_radar_excel import (
    SellerRadarExcelAdapter,
    seller_sheet_name,
)


def test_limit_defaults_and_clamps():
    assert safe_limit(50) == 50
    assert safe_limit(0) == 1
    assert safe_limit(5000) == 1000


def test_short_sheet_name():
    assert seller_sheet_name("cardshop123") == (
        "Seller - cardshop123"
    )


def test_long_sheet_name_is_stable_and_valid():
    value = seller_sheet_name(
        "a-very-long-ebay-seller-username-that-exceeds-excel"
    )
    assert len(value) <= 31
    assert value == seller_sheet_name(
        "a-very-long-ebay-seller-username-that-exceeds-excel"
    )


def test_invalid_sheet_characters_removed():
    value = seller_sheet_name("abc/def:*?[]")
    assert all(char not in value for char in "[]:*?/\\")


def test_listing_type():
    assert listing_type(
        {"buyingOptions": ["AUCTION"]}
    ) == "AUCTION"
    assert listing_type(
        {"buyingOptions": ["FIXED_PRICE"]}
    ) == "BUY IT NOW"
    assert listing_type(
        {
            "buyingOptions": [
                "AUCTION",
                "FIXED_PRICE",
            ]
        }
    ) == "AUCTION + BUY IT NOW"


def test_displayed_price_prefers_bid():
    item = {
        "currentBidPrice": {"value": "4.50"},
        "price": {"value": "9.99"},
    }
    assert displayed_price(item) == 4.5


def test_result_row_links_are_beside_ratios():
    candidate = SimpleNamespace(
        name="Pikachu",
        set_name="Base Set",
        number="58",
        variant="Normal",
        card_id="base1-58",
        rarity="Common",
        image_url="https://example/image",
    )
    result = SimpleNamespace(
        candidate=candidate,
        decision="GREEN",
        recommended_action="BID",
        score=90,
        listing_type="AUCTION",
        seller="seller",
        title="Pikachu Base Set 58/102",
        item_id="v1|123456789012|0",
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
        minutes_remaining=30,
        bid_count=1,
        feedback_percent=100,
        feedback_count=100,
        condition="Ungraded",
        condition_flag="AMBER",
        condition_details="Inspect",
        match_confidence="High",
        search_query="Pikachu Base Set 58",
        item_url="https://example/listing",
        auction_search_url="https://example/auction",
        buy_now_search_url="https://example/buy",
        sold_search_url="https://example/sold",
        notes="",
    )
    row = SellerRadarExcelAdapter._result_row(
        1,
        result,
        "",
    )
    assert len(row) == 50
    assert row[22:31] == [
        "Open Listing",
        "Open Card Image",
        "Open Auction Search",
        "Open Buy Now Search",
        "Open Sold Results",
        "Open UK Market",
        "Open TCGplayer",
        "Open Cardmarket",
        "Open PriceCharting",
    ]
