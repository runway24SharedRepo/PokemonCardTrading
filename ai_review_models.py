from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ListingAIReview(BaseModel):
    """Strict text-only review returned by the OpenAI Responses API."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal[
        "CONFIRMED",
        "REJECTED",
        "AMBIGUOUS",
        "NOT_A_SINGLE_CARD",
        "INSUFFICIENT_DATA",
    ]
    selected_candidate_key: str = Field(
        description=(
            "Exactly one key from the supplied candidate shortlist, or an "
            "empty string when no exact candidate can be confirmed."
        )
    )
    confidence_percent: int = Field(ge=0, le=100)
    edition_verdict: Literal[
        "STANDARD_OR_UNLIMITED",
        "FIRST_EDITION",
        "SHADOWLESS",
        "OTHER",
        "UNKNOWN",
    ]
    variant_verdict: Literal[
        "NORMAL",
        "HOLOFOIL",
        "REVERSE_HOLOFOIL",
        "V",
        "VMAX",
        "VSTAR",
        "EX",
        "GX",
        "BREAK",
        "LV_X",
        "OTHER",
        "UNKNOWN",
    ]
    listing_risk: Literal["LOW", "MEDIUM", "HIGH", "BLOCK"]
    risk_flags: list[str]
    condition_summary: str
    long_term_note: str
    evidence: list[str]


@dataclass(frozen=True)
class CandidateOption:
    candidate_key: str
    card_id: str
    card_name: str
    set_name: str
    card_number: str
    variant: str
    market_value_gbp: float = 0.0

    def to_prompt_dict(self) -> dict[str, object]:
        return {
            "candidate_key": self.candidate_key,
            "card_id": self.card_id,
            "card_name": self.card_name,
            "set_name": self.set_name,
            "card_number": self.card_number,
            "variant": self.variant,
            "market_value_gbp": round(float(self.market_value_gbp or 0), 2),
        }


@dataclass
class ListingRow:
    sheet_name: str
    row_number: int
    header_row: int
    item_id: str
    title: str
    card_id: str
    card_name: str
    set_name: str
    card_number: str
    variant: str
    market_value_gbp: float
    decision: str
    match_confidence: str
    condition: str
    condition_details: str
    seller: str
    minutes_remaining: float | None
    review_request: str
    ai_columns: dict[str, int] = field(default_factory=dict)

    @property
    def current_candidate_key(self) -> str:
        return make_candidate_key(self.card_id, self.variant)


@dataclass
class APIUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class ReviewExecution:
    review: ListingAIReview
    usage: APIUsage
    model: str
    cached: bool
    fingerprint: str
    response_id: str = ""


def make_candidate_key(card_id: str, variant: str) -> str:
    return f"{str(card_id or '').strip()}::{str(variant or '').strip()}"
