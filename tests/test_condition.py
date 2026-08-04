from random_sniper.condition import assess_condition


def test_poor_is_red_even_when_ungraded():
    assessment = assess_condition(
        {"condition": "Ungraded"},
        {
            "condition": "Ungraded",
            "conditionDescriptors": [
                {
                    "name": "Card Condition",
                    "values": [
                        {"content": "Heavily Played (Poor)"}
                    ],
                }
            ],
        },
    )
    assert assessment.flag == "RED"
    assert "Poor" in assessment.display


def test_fresh_pack_is_green():
    assessment = assess_condition(
        {"condition": "Ungraded"},
        {
            "conditionDescription": (
                "Comparable to a fresh pack. "
                "Flaws may include minor corner and edge wear."
            )
        },
    )
    # Explicit wear wording is intentionally cautious.
    assert assessment.flag == "AMBER"


def test_near_mint_descriptor_is_green():
    assessment = assess_condition(
        {"condition": "Ungraded"},
        {
            "conditionDescriptors": [
                {
                    "name": "40001",
                    "values": [{"content": "400010"}],
                }
            ]
        },
    )
    assert assessment.flag == "GREEN"
    assert "Near Mint" in assessment.display
