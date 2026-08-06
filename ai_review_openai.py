from __future__ import annotations

import json
from typing import Any

from ai_review_logic import review_fingerprint
from ai_review_models import APIUsage, CandidateOption, ListingAIReview, ListingRow, ReviewExecution


PROMPT_VERSION = "pokemon-listing-text-review-v1"

SYSTEM_PROMPT = """
You are a conservative Pokémon TCG listing adjudicator.

You receive text from one eBay listing, the spreadsheet's current card assignment,
and a restricted shortlist of database candidates.

Hard rules:
- Use only the supplied text. There are no images in this review.
- Never invent a card or candidate key.
- selected_candidate_key must be exactly one supplied key, or an empty string.
- Confirm only when card name/form, collector number, set and variant/edition
  evidence are compatible.
- In a fraction such as 053/102, the numerator identifies the card. The
  denominator never identifies it. Leading zeroes are equivalent.
- First Edition requires explicit 1st Edition/First Edition wording.
- An unmarked vintage card defaults to standard/Unlimited.
- Unlimited explicitly rejects First Edition.
- Shadowless requires explicit Shadowless wording.
- Distinguish V, VMAX, VSTAR, EX, GX, BREAK, LV.X and standard cards.
- Distinguish regular Holo, Reverse Holo and non-Holo when text is explicit.
- Flag proxy, custom, replica, fake, novelty metal/gold cards, World
  Championship versions, jumbo cards, code cards, lots and stock-photo risks.
- When evidence conflicts or is incomplete, return AMBIGUOUS or
  INSUFFICIENT_DATA instead of guessing.
- Keep evidence concise and factual.
- long_term_note is not a price forecast. State only material collection risk.
""".strip()

MODEL_PRICES_USD_PER_MILLION = {
    "gpt-5.6-luna": {"input": 1.00, "cached_input": 0.10, "output": 6.00},
    "gpt-5.6-terra": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.6-sol": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
    "gpt-5.6": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
}


def estimate_cost(
    model: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> float:
    pricing = MODEL_PRICES_USD_PER_MILLION.get(model)
    if pricing is None:
        raise RuntimeError(
            f"Cost table is unavailable for model {model!r}. Use gpt-5.6-luna, "
            "gpt-5.6-terra or gpt-5.6-sol."
        )
    cached = max(0, min(int(cached_input_tokens), int(input_tokens)))
    uncached = max(0, int(input_tokens) - cached)
    cost = (
        uncached * pricing["input"]
        + cached * pricing["cached_input"]
        + int(output_tokens) * pricing["output"]
    ) / 1_000_000
    return round(cost, 8)


def usage_from_response(response: Any, model: str) -> APIUsage:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    details = getattr(usage, "input_tokens_details", None)
    cached_input_tokens = int(getattr(details, "cached_tokens", 0) or 0)
    return APIUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost(
            model, input_tokens, cached_input_tokens, output_tokens
        ),
    )


class OpenAIListingReviewer:
    def __init__(
        self,
        model: str,
        reasoning_effort: str = "low",
        maximum_output_tokens: int = 650,
    ) -> None:
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.maximum_output_tokens = max(200, int(maximum_output_tokens))
        from openai import OpenAI

        self.client = OpenAI()

    def build_payload(
        self,
        row: ListingRow,
        candidates: list[CandidateOption],
        details: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        listing_payload = {
            "source_sheet": row.sheet_name,
            "listing_title": row.title,
            "item_id": row.item_id,
            "spreadsheet_assignment": {
                "candidate_key": row.current_candidate_key,
                "card_id": row.card_id,
                "card_name": row.card_name,
                "set_name": row.set_name,
                "card_number": row.card_number,
                "variant": row.variant,
                "market_value_gbp": round(row.market_value_gbp, 2),
                "deterministic_match_confidence": row.match_confidence,
            },
            "spreadsheet_condition": {
                "condition": row.condition,
                "condition_details": row.condition_details,
            },
            "ebay_text_details": details,
        }
        fingerprint = review_fingerprint(
            model=self.model,
            prompt_version=PROMPT_VERSION,
            listing_payload=listing_payload,
            candidates=candidates,
        )
        return {
            "listing": listing_payload,
            "candidate_shortlist": [candidate.to_prompt_dict() for candidate in candidates],
            "required_task": (
                "Adjudicate whether the spreadsheet assignment is the exact "
                "text-supported identity."
            ),
        }, fingerprint

    def review(
        self,
        row: ListingRow,
        candidates: list[CandidateOption],
        details: dict[str, Any],
    ) -> ReviewExecution:
        user_payload, fingerprint = self.build_payload(row, candidates, details)
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        user_payload, ensure_ascii=False, separators=(",", ":")
                    ),
                },
            ],
            text_format=ListingAIReview,
            reasoning={"effort": self.reasoning_effort},
            max_output_tokens=self.maximum_output_tokens,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no parsed structured review.")
        allowed = {candidate.candidate_key for candidate in candidates}
        selected = parsed.selected_candidate_key.strip()
        if selected and selected not in allowed:
            raise RuntimeError("OpenAI selected a candidate outside the supplied shortlist.")
        return ReviewExecution(
            review=parsed,
            usage=usage_from_response(response, self.model),
            model=self.model,
            cached=False,
            fingerprint=fingerprint,
            response_id=str(getattr(response, "id", "") or ""),
        )
