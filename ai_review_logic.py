from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from ai_review_models import CandidateOption, ListingAIReview, ListingRow


RISK_TERMS = (
    "proxy", "custom", "fan made", "fanmade", "reprint", "replica", "fake",
    "metal card", "gold card", "world championship", "jumbo", "oversized",
    "code card", "digital code", "job lot", "bundle", "mystery",
    "photo is an example", "card may differ", "not the card pictured",
    "stock photo",
)
EDITION_TERMS = (
    "1st edition", "first edition", "1st ed", "unlimited", "shadowless",
)


def normalise(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tokens(value: Any) -> set[str]:
    return {token for token in normalise(value).split() if len(token) >= 2}


def canonical_number(value: Any) -> str:
    text = normalise(value).replace(" ", "")
    if "/" in text:
        text = text.split("/", 1)[0]
    match = re.fullmatch(r"([a-z]*)(\d+)", text)
    if not match:
        return text
    prefix, digits = match.groups()
    return f"{prefix}{int(digits)}"


def title_collector_numbers(title: str) -> set[str]:
    compact = normalise(title).replace(" ", "")
    output: set[str] = set()
    for numerator, _ in re.findall(
        r"(?<![a-z0-9])([a-z]{0,6}\d{1,4})/([a-z]{0,6}\d{1,4})(?![a-z0-9])",
        compact,
    ):
        output.add(canonical_number(numerator))
    for value in re.findall(
        r"(?<![a-z0-9])([a-z]{1,6}\d{1,4})(?![a-z0-9])", compact
    ):
        output.add(canonical_number(value))
    return output


def candidate_score(listing_title: str, candidate: CandidateOption) -> float:
    title_tokens = tokens(listing_title)
    name_tokens = tokens(candidate.card_name)
    set_tokens = tokens(candidate.set_name)
    name_score = len(title_tokens & name_tokens) / max(1, len(name_tokens))
    set_score = len(title_tokens & set_tokens) / max(1, len(set_tokens))
    expected_number = canonical_number(candidate.card_number)
    number_score = 1.0 if expected_number in title_collector_numbers(listing_title) else 0.0
    variant_tokens = tokens(candidate.variant)
    variant_score = (
        len(title_tokens & variant_tokens) / max(1, len(variant_tokens))
        if variant_tokens else 0.5
    )
    return 0.48 * name_score + 0.30 * number_score + 0.15 * set_score + 0.07 * variant_score


def build_candidate_shortlist(
    row: ListingRow,
    all_candidates: Iterable[CandidateOption],
    maximum: int = 5,
) -> list[CandidateOption]:
    candidates = list(all_candidates)
    current_key = row.current_candidate_key
    current = next((c for c in candidates if c.candidate_key == current_key), None)
    row_number = canonical_number(row.card_number)
    row_name_tokens = tokens(row.card_name)
    title_numbers = title_collector_numbers(row.title)

    pool: list[tuple[float, CandidateOption]] = []
    for candidate in candidates:
        candidate_number = canonical_number(candidate.card_number)
        candidate_name_tokens = tokens(candidate.card_name)
        related_name = bool(
            row_name_tokens
            and candidate_name_tokens
            and (
                row_name_tokens <= candidate_name_tokens
                or candidate_name_tokens <= row_name_tokens
                or len(row_name_tokens & candidate_name_tokens)
                >= max(1, min(len(row_name_tokens), len(candidate_name_tokens)) - 1)
            )
        )
        related_number = bool(
            candidate_number
            and (candidate_number == row_number or candidate_number in title_numbers)
        )
        if candidate.candidate_key != current_key and not (related_name and related_number):
            continue
        score = candidate_score(row.title, candidate)
        if candidate.candidate_key == current_key:
            score += 0.05
        pool.append((score, candidate))

    pool.sort(key=lambda pair: (pair[0], pair[1].market_value_gbp), reverse=True)
    output: list[CandidateOption] = []
    seen: set[str] = set()
    if current is not None:
        output.append(current)
        seen.add(current.candidate_key)
    for _, candidate in pool:
        if candidate.candidate_key in seen:
            continue
        output.append(candidate)
        seen.add(candidate.candidate_key)
        if len(output) >= maximum:
            break
    if not output:
        output.append(
            CandidateOption(
                candidate_key=current_key,
                card_id=row.card_id,
                card_name=row.card_name,
                set_name=row.set_name,
                card_number=row.card_number,
                variant=row.variant,
                market_value_gbp=row.market_value_gbp,
            )
        )
    return output[:maximum]


@dataclass(frozen=True)
class ReviewPolicy:
    minimum_market_value_gbp: float = 20.0
    review_decisions: tuple[str, ...] = ("GREEN", "AMBER")
    review_low_confidence: bool = True
    review_risk_terms: bool = True
    review_edition_terms: bool = True
    include_archives: bool = False
    urgent_max_minutes: int = 180


def contains_any(value: str, terms: Iterable[str]) -> bool:
    normalized = normalise(value)
    return any(normalise(term) in normalized for term in terms)


def should_review(row: ListingRow, mode: str, policy: ReviewPolicy) -> bool:
    request = normalise(row.review_request or "AUTO").upper()
    if request == "NO":
        return False
    if request == "YES":
        return True
    sheet = row.sheet_name.casefold()
    is_archive = "history" in sheet or "archive" in sheet
    if is_archive and not policy.include_archives:
        return False
    if mode == "selected":
        return False
    if mode == "urgent":
        if "queue" not in sheet:
            return False
        return row.minutes_remaining is None or row.minutes_remaining <= policy.urgent_max_minutes

    decision_ok = row.decision.strip().upper() in {d.upper() for d in policy.review_decisions}
    market_ok = row.market_value_gbp >= policy.minimum_market_value_gbp
    low_confidence = policy.review_low_confidence and normalise(row.match_confidence) not in {
        "high", "exact", "very high"
    }
    risk_term = policy.review_risk_terms and contains_any(row.title, RISK_TERMS)
    edition_term = policy.review_edition_terms and contains_any(row.title, EDITION_TERMS)
    return (decision_ok and market_ok) or low_confidence or risk_term or edition_term


def review_priority(row: ListingRow) -> tuple[int, int, int, float, float]:
    manual = 0 if normalise(row.review_request).upper() == "YES" else 1
    decision_order = {"GREEN": 0, "AMBER": 1, "RED": 2}.get(
        row.decision.strip().upper(), 3
    )
    confidence_order = 0 if normalise(row.match_confidence) not in {
        "high", "exact", "very high"
    } else 1
    minutes = float(row.minutes_remaining) if row.minutes_remaining is not None else 10**9
    return manual, decision_order, confidence_order, -float(row.market_value_gbp or 0), minutes


def derive_action(
    review: ListingAIReview,
    current_candidate_key: str,
    auto_accept_confidence: int,
) -> tuple[str, str]:
    selected = review.selected_candidate_key.strip()
    if (
        review.verdict == "CONFIRMED"
        and selected == current_candidate_key
        and review.confidence_percent >= auto_accept_confidence
        and review.listing_risk not in {"HIGH", "BLOCK"}
    ):
        return "CONFIRMED", "KEEP"
    if (
        review.verdict in {"REJECTED", "NOT_A_SINGLE_CARD"}
        or (selected and selected != current_candidate_key and review.confidence_percent >= 80)
        or review.listing_risk == "BLOCK"
    ):
        return "REJECTED", "BLOCK"
    return "MANUAL REVIEW", "MANUAL REVIEW"


def review_fingerprint(
    *,
    model: str,
    prompt_version: str,
    listing_payload: dict[str, Any],
    candidates: list[CandidateOption],
) -> str:
    payload = {
        "model": model,
        "prompt_version": prompt_version,
        "listing": listing_payload,
        "candidates": [candidate.to_prompt_dict() for candidate in candidates],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
