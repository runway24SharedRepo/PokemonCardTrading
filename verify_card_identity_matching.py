from random_sniper.core import Candidate, listing_match_score
from random_sniper.seller_discovery import CandidateTitleMatcher


def card(name, set_name, number, card_id):
    return Candidate(
        card_id=card_id,
        name=name,
        set_name=set_name,
        number=number,
        variant="Holofoil",
        market_value=20,
        source="verification",
        source_date="2026-08-05",
        source_url="https://example",
        supertype="Pokémon",
    )


cases = [
    (
        "Pokémon TCG Perfect Order Luxray Regular Holo Rare 028/88 NM",
        card("Luxray", "Legends Awakened", "8", "wrong-luxray"),
        card("Luxray", "Perfect Order", "28", "correct-luxray"),
    ),
    (
        "Pokémon TCG Mawile VSTAR Silver Tempest 071/195 Holo Ultra Rare",
        card("Mawile", "Crystal Guardians", "9", "wrong-mawile"),
        card("Mawile VSTAR", "Silver Tempest", "71", "correct-mawile"),
    ),
]

for title, wrong, correct in cases:
    wrong_score, _ = listing_match_score(wrong, title, [])
    detected = CandidateTitleMatcher(
        [wrong, correct]
    ).match(title, [])
    assert wrong_score == 0
    assert detected is correct

print("Exact card-identity verification passed.")
print("Luxray 028/88 is not Luxray 8.")
print("Mawile VSTAR 071/195 is not Mawile 9.")
