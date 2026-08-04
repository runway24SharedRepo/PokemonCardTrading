from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from random_range_sniper import evaluate_item
from random_sniper.core import Candidate


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


def item(hours):
    return {
        "title": "Pikachu Base Set 58/102 Pokemon Card",
        "itemId": f"item-{hours}",
        "itemWebUrl": "https://www.ebay.co.uk/itm/example",
        "buyingOptions": ["AUCTION"],
        "currentBidPrice": {"value": "5.00"},
        "shippingOptions": [{"shippingCost": {"value": "1.50"}}],
        "itemEndDate": (
            datetime.now(timezone.utc) + timedelta(hours=hours)
        ).isoformat(),
        "seller": {
            "username": "seller",
            "feedbackPercentage": "99.5",
            "feedbackScore": 1000,
        },
        "bidCount": 1,
        "condition": "Used",
    }


def settings():
    return SimpleNamespace(
        maximum_postage=None,
        target_ratio=0.75,
        ending_within_hours=24.0,
        minimum_feedback=98.0,
    )


def test_outside_window_still_appears_in_results():
    result = evaluate_item(
        candidate(),
        item(48),
        "Pikachu Base 58",
        settings(),
        [],
    )
    assert result is not None
    assert result.within_sniping_window is False
    assert "outside" in result.notes.casefold()


def test_inside_window_is_queue_eligible():
    result = evaluate_item(
        candidate(),
        item(2),
        "Pikachu Base 58",
        settings(),
        [],
    )
    assert result is not None
    assert result.within_sniping_window is True
