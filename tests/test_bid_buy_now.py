from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from random_range_sniper import evaluate_item
from random_sniper.core import Candidate, overall_decision, recommended_action


def candidate():
    return Candidate(
        card_id="base1-58",
        name="Pikachu",
        set_name="Base",
        number="58",
        variant="Normal",
        market_value=20.0,
        source="test",
        source_date="2026-08-04",
        source_url="https://example",
    )


def settings():
    return SimpleNamespace(
        maximum_postage=None,
        target_ratio=0.75,
        ending_within_hours=24.0,
        minimum_feedback=98.0,
    )


def base_item():
    return {
        "title": "Pikachu Base Set 58/102 Pokemon Card",
        "itemId": "item-1",
        "itemWebUrl": "https://www.ebay.co.uk/itm/example",
        "shippingOptions": [{"shippingCost": {"value": "1.50"}}],
        "itemEndDate": (
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).isoformat(),
        "seller": {
            "username": "seller",
            "feedbackPercentage": "99.5",
            "feedbackScore": 1000,
        },
        "bidCount": 1,
        "condition": "Used",
    }


def test_auction_and_buy_now_are_separate():
    item = base_item()
    item.update({
        "buyingOptions": ["AUCTION", "FIXED_PRICE"],
        "currentBidPrice": {"value": "5.00"},
        "price": {"value": "12.00"},
    })
    result = evaluate_item(candidate(), item, "Pikachu Base 58", settings(), [])
    assert result is not None
    assert result.listing_type == "AUCTION + BUY IT NOW"
    assert result.current_bid == 5.00
    assert result.buy_now_price == 12.00
    assert result.bid_delivered == 6.50
    assert result.buy_now_delivered == 13.50
    assert result.bid_decision == "GREEN"
    assert result.buy_now_decision == "GREEN"
    assert result.recommended_action == "BID OR BUY NOW"


def test_fixed_price_only_is_buy_now_scenario():
    item = base_item()
    item.update({
        "buyingOptions": ["FIXED_PRICE"],
        "price": {"value": "10.00"},
    })
    result = evaluate_item(candidate(), item, "Pikachu Base 58", settings(), [])
    assert result is not None
    assert result.current_bid is None
    assert result.buy_now_price == 10.00
    assert result.bid_decision == "N/A"
    assert result.buy_now_decision == "GREEN"
    assert result.queue_eligible is True


def test_action_helpers():
    assert overall_decision("AMBER", "GREEN") == "GREEN"
    assert recommended_action("GREEN", "RED", True) == "BID / SNIPE"
    assert recommended_action("RED", "GREEN", False) == "BUY NOW"
