from ai_review_logic import ReviewPolicy, build_candidate_shortlist, derive_action, should_review
from ai_review_models import CandidateOption, ListingAIReview, ListingRow


def row(**overrides):
    values = dict(
        sheet_name="Random Snipe Queue",
        row_number=5,
        header_row=4,
        item_id="v1|123|0",
        title="Pokemon Magnemite 53/102 Base Set Unlimited Common",
        card_id="base1-53",
        card_name="Magnemite",
        set_name="Base",
        card_number="53",
        variant="Normal",
        market_value_gbp=25,
        decision="GREEN",
        match_confidence="High",
        condition="Ungraded",
        condition_details="Near Mint",
        seller="seller",
        minutes_remaining=60,
        review_request="AUTO",
    )
    values.update(overrides)
    return ListingRow(**values)


def option(card_id, set_name, number, variant, value=10):
    return CandidateOption(
        candidate_key=f"{card_id}::{variant}",
        card_id=card_id,
        card_name="Magnemite",
        set_name=set_name,
        card_number=number,
        variant=variant,
        market_value_gbp=value,
    )


def review(**overrides):
    values = dict(
        verdict="CONFIRMED",
        selected_candidate_key="base1-53::Normal",
        confidence_percent=98,
        edition_verdict="STANDARD_OR_UNLIMITED",
        variant_verdict="NORMAL",
        listing_risk="LOW",
        risk_flags=[],
        condition_summary="Near Mint wording",
        long_term_note="No text-only concern",
        evidence=["53/102", "Unlimited"],
    )
    values.update(overrides)
    return ListingAIReview(**values)


def test_smart_review_selects_green_value_row():
    assert should_review(row(), "smart", ReviewPolicy(minimum_market_value_gbp=20))


def test_no_request_excludes_row():
    assert not should_review(row(review_request="NO"), "smart", ReviewPolicy())


def test_selected_mode_only_uses_yes():
    assert should_review(row(review_request="YES"), "selected", ReviewPolicy())
    assert not should_review(row(review_request="AUTO"), "selected", ReviewPolicy())


def test_candidate_shortlist_keeps_current_and_alternative():
    current = option("base1-53", "Base", "53", "Normal")
    first = option("base1-53", "Base", "53", "1st Edition Normal", 30)
    unrelated = CandidateOption(
        candidate_key="xy-1::Normal",
        card_id="xy-1",
        card_name="Pikachu",
        set_name="XY",
        card_number="1",
        variant="Normal",
        market_value_gbp=5,
    )
    shortlist = build_candidate_shortlist(row(), [first, unrelated, current])
    keys = [value.candidate_key for value in shortlist]
    assert keys[0] == current.candidate_key
    assert first.candidate_key in keys
    assert unrelated.candidate_key not in keys


def test_keep_requires_same_candidate_and_high_confidence():
    assert derive_action(review(), "base1-53::Normal", 95) == ("CONFIRMED", "KEEP")


def test_different_candidate_blocks_when_confident():
    assert derive_action(
        review(
            selected_candidate_key="base1-53::1st Edition Normal",
            confidence_percent=90,
        ),
        "base1-53::Normal",
        95,
    ) == ("REJECTED", "BLOCK")


def test_ambiguous_goes_to_manual_review():
    assert derive_action(
        review(verdict="AMBIGUOUS", selected_candidate_key="", confidence_percent=60),
        "base1-53::Normal",
        95,
    ) == ("MANUAL REVIEW", "MANUAL REVIEW")
