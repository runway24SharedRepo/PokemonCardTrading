from live_radar.condition import assess_condition


def test_poor_is_red():
    assessment = assess_condition(
        {"condition": "Ungraded"},
        {
            "condition": "Ungraded",
            "conditionDescriptors": [
                {
                    "name": "Card Condition",
                    "values": [
                        {
                            "content":
                            "Heavily Played (Poor)"
                        }
                    ],
                }
            ],
        },
    )
    assert assessment.flag == "RED"
    assert "Poor" in assessment.display


def test_ungraded_without_detail_is_amber():
    assessment = assess_condition(
        {"condition": "Ungraded"},
    )
    assert assessment.flag == "AMBER"


def test_near_mint_descriptor_is_green():
    assessment = assess_condition(
        {"condition": "Ungraded"},
        {
            "conditionDescriptors": [
                {
                    "name": "40001",
                    "values": [
                        {"content": "400010"}
                    ],
                }
            ],
        },
    )
    assert assessment.flag == "GREEN"
