from pathlib import Path

from ai_review_cache import AIReviewCache
from ai_review_models import APIUsage, ListingAIReview, ReviewExecution


def test_cache_round_trip(tmp_path: Path):
    cache = AIReviewCache(tmp_path / "cache.sqlite")
    try:
        review = ListingAIReview(
            verdict="CONFIRMED",
            selected_candidate_key="base1-53::Normal",
            confidence_percent=98,
            edition_verdict="STANDARD_OR_UNLIMITED",
            variant_verdict="NORMAL",
            listing_risk="LOW",
            risk_flags=[],
            condition_summary="NM",
            long_term_note="No concern",
            evidence=["53/102"],
        )
        execution = ReviewExecution(
            review=review,
            usage=APIUsage(input_tokens=1000, output_tokens=100, estimated_cost_usd=0.0016),
            model="gpt-5.6-luna",
            cached=False,
            fingerprint="abc",
            response_id="resp_123",
        )
        cache.put_review(execution)
        loaded = cache.get_review("abc")
        assert loaded is not None
        assert loaded.cached
        assert loaded.review.verdict == "CONFIRMED"
        assert cache.current_month_spend() == 0.0016
    finally:
        cache.close()
