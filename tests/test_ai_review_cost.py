from ai_review_openai import estimate_cost


def test_luna_cost_calculation():
    assert estimate_cost("gpt-5.6-luna", 1000, 0, 200) == 0.0022


def test_cached_tokens_use_cached_rate():
    assert estimate_cost("gpt-5.6-luna", 1000, 1000, 0) == 0.0001
