from random_sniper.core import (
    Candidate,
    card_number_match,
    collector_number_evidence,
    listing_match_score,
)
from random_sniper.seller_discovery import CandidateTitleMatcher
from live_radar.core import (
    Candidate as LiveCandidate,
    CandidateTitleMatcher as LiveMatcher,
    listing_match_score as live_listing_match_score,
)


def candidate(name, set_name, number, card_id, variant="Holofoil"):
    return Candidate(
        card_id=card_id,
        name=name,
        set_name=set_name,
        number=number,
        variant=variant,
        market_value=20,
        source="test",
        source_date="2026-08-05",
        source_url="https://example",
        supertype="Pokémon",
    )


def live_candidate(name, set_name, number, card_id, variant="Holofoil"):
    return LiveCandidate(
        card_id=card_id,
        name=name,
        set_name=set_name,
        number=number,
        variant=variant,
        market_value=20,
        source="test",
        source_date="2026-08-05",
        source_url="https://example",
        supertype="Pokémon",
    )


LUXRAY_TITLE = (
    "Pokémon TCG Perfect Order Luxray Regular "
    "Holo Rare 028/88 NM"
)
MAWILE_TITLE = (
    "Pokémon TCG Mawile VSTAR Silver Tempest "
    "071/195 Holo Ultra Rare"
)


def test_single_digit_does_not_match_fraction_numerator():
    score, conflict, reason = collector_number_evidence(
        LUXRAY_TITLE,
        "8",
    )
    assert score == 0
    assert conflict is True
    assert "028/88" in reason


def test_denominator_never_identifies_the_card():
    assert card_number_match(LUXRAY_TITLE, "88") == 0


def test_leading_zeroes_match_the_correct_numerator():
    assert card_number_match(LUXRAY_TITLE, "28") == 1.0
    assert card_number_match(LUXRAY_TITLE, "028") == 1.0


def test_wrong_luxray_identity_is_rejected():
    wrong = candidate(
        "Luxray",
        "Legends Awakened",
        "8",
        "la-8",
    )
    score, reason = listing_match_score(
        wrong,
        LUXRAY_TITLE,
        [],
    )
    assert score == 0
    assert "Collector-number conflict" in reason


def test_correct_luxray_identity_is_selected():
    correct = candidate(
        "Luxray",
        "Perfect Order",
        "28",
        "po-28",
    )
    wrong = candidate(
        "Luxray",
        "Legends Awakened",
        "8",
        "la-8",
    )
    matcher = CandidateTitleMatcher([wrong, correct])
    assert matcher.match(LUXRAY_TITLE, []) is correct


def test_wrong_mawile_identity_is_rejected():
    wrong = candidate(
        "Mawile",
        "Crystal Guardians",
        "9",
        "cg-9",
    )
    score, reason = listing_match_score(
        wrong,
        MAWILE_TITLE,
        [],
    )
    assert score == 0
    assert (
        "Card-form conflict" in reason
        or "Collector-number conflict" in reason
    )


def test_correct_mawile_vstar_identity_is_selected():
    correct = candidate(
        "Mawile VSTAR",
        "Silver Tempest",
        "71",
        "st-71",
    )
    wrong = candidate(
        "Mawile",
        "Crystal Guardians",
        "9",
        "cg-9",
    )
    matcher = CandidateTitleMatcher([wrong, correct])
    assert matcher.match(MAWILE_TITLE, []) is correct


def test_vstar_title_does_not_match_plain_or_v_card():
    plain = candidate(
        "Mawile",
        "Example",
        "71",
        "plain-71",
    )
    v_card = candidate(
        "Mawile V",
        "Example",
        "71",
        "v-71",
    )
    for value in (plain, v_card):
        score, reason = listing_match_score(
            value,
            MAWILE_TITLE,
            [],
        )
        assert score == 0
        assert "Card-form conflict" in reason


def test_alphanumeric_promo_identifier_is_exact():
    title = "Kyogre EX Black Star Promo XY41 Holo NM"
    assert card_number_match(title, "XY41") >= 0.82
    assert card_number_match(title, "XY4") == 0


def test_explicit_reverse_holo_conflict_is_rejected():
    regular = candidate(
        "Pikachu",
        "Example",
        "28",
        "example-28",
        variant="Holofoil",
    )
    score, reason = listing_match_score(
        regular,
        "Pikachu Example 028/100 Reverse Holo",
        [],
    )
    assert score == 0
    assert "Variant conflict" in reason


def test_ambiguous_same_name_and_number_is_not_guessed():
    first = candidate(
        "Pikachu",
        "First Set",
        "25",
        "first-25",
    )
    second = candidate(
        "Pikachu",
        "Second Set",
        "25",
        "second-25",
    )
    matcher = CandidateTitleMatcher([first, second])
    assert matcher.match(
        "Pokemon Pikachu 25 Holo NM",
        [],
    ) is None


def test_live_mode_uses_the_same_identity_rules():
    wrong = live_candidate(
        "Luxray",
        "Legends Awakened",
        "8",
        "la-8",
    )
    correct = live_candidate(
        "Luxray",
        "Perfect Order",
        "28",
        "po-28",
    )

    wrong_score, wrong_reason = live_listing_match_score(
        wrong,
        LUXRAY_TITLE,
        [],
    )
    assert wrong_score == 0
    assert "Collector-number conflict" in wrong_reason

    matched, score, reason = LiveMatcher(
        [wrong, correct]
    ).match(LUXRAY_TITLE, [])
    assert matched is correct
    assert score >= 0.72
    assert reason == ""
