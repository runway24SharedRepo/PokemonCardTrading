from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import quote_plus


@dataclass
class Candidate:
    card_id: str
    name: str
    set_name: str
    number: str
    variant: str
    market_value: float
    source: str
    source_date: Any
    source_url: str
    rarity: str = ""
    supertype: str = ""
    image_url: str = ""

    @property
    def identity(self) -> str:
        base = self.card_id or (
            f"{self.name}|{self.set_name}|{self.number}"
        )
        return f"{base}|{self.variant}".casefold()


@dataclass
class RadarSettings:
    enabled: bool = True
    target_ratio: float = 0.75
    amber_upper_ratio: float = 0.90
    minimum_market_value: float = 3.0
    maximum_delivered_cost: float = 100.0
    results_per_request: int = 200
    maximum_broad_requests: int = 5
    minimum_minutes_remaining: int = 2
    maximum_hours_remaining: float = 24.0
    minimum_feedback: float = 98.0
    minimum_feedback_count: int = 25
    maximum_total_api_calls: int = 100
    maximum_live_rows: int = 250
    broad_query: str = "pokemon card"
    expand_green_sellers: bool = True
    maximum_green_sellers: int = 5
    seller_listing_limit: int = 100
    opportunities_per_seller: int = 5
    maximum_condition_checks: int = 50
    archive_previous_results: bool = True


@dataclass
class RadarResult:
    candidate: Candidate
    title: str
    item_id: str
    item_url: str
    listing_image_url: str
    current_bid: float
    postage: float
    delivered: float
    market_value: float
    ratio: float
    target_delivered: float
    maximum_bid: float
    bid_headroom: float
    decision: str
    recommended_action: str
    score: float
    end_time: datetime
    minutes_remaining: int
    bid_count: int
    seller: str
    feedback_percent: float
    feedback_count: int
    condition: str
    condition_flag: str
    condition_details: str
    match_score: float
    match_confidence: str
    search_query: str
    direct_search_url: str
    sold_search_url: str
    discovery_source: str = "BROAD RADAR"
    parent_item_id: str = ""
    notes: str = ""

    @property
    def card_label(self) -> str:
        return (
            f"{self.candidate.name} | {self.candidate.set_name} | "
            f"{self.candidate.number} | {self.candidate.variant}"
        )


def normalize_card_number(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return str(int(value))
        return format(value, "g")

    text = str(value).strip()
    match = re.fullmatch(r"([+-]?\d+)\.0+", text)
    return match.group(1) if match else text


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = text.casefold().replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def meaningful_tokens(value: str) -> list[str]:
    ignored = {
        "pokemon", "card", "cards", "tcg", "the", "and", "of", "set",
        "edition", "rare", "trading", "game", "holo", "reverse", "foil",
    }
    return [
        token
        for token in normalize_text(value).split()
        if len(token) >= 2 and token not in ignored
    ]


def variant_keywords(variant: str) -> str:
    value = normalize_text(variant)
    if value in {"", "normal"}:
        return ""
    if "reverse" in value:
        return "reverse holo"
    if ("1st" in value or "first" in value) and "holo" in value:
        return "1st edition holo"
    if "1st" in value or "first" in value:
        return "1st edition"
    if "holo" in value:
        return "holo"
    return variant


def exact_card_query(candidate: Candidate) -> str:
    parts = [
        candidate.name,
        candidate.set_name,
        candidate.number,
        variant_keywords(candidate.variant),
    ]
    return re.sub(
        r"\s+",
        " ",
        " ".join(str(value or "") for value in parts),
    ).strip()


def ebay_direct_search_url(query: str) -> str:
    return (
        "https://www.ebay.co.uk/sch/i.html?"
        f"_nkw={quote_plus(query)}"
        "&_sacat=0&LH_Auction=1&LH_PrefLoc=1&_sop=1"
    )


def ebay_sold_search_url(query: str) -> str:
    return (
        "https://www.ebay.co.uk/sch/i.html?"
        f"_nkw={quote_plus(query)}"
        "&_sacat=0&LH_Sold=1&LH_Complete=1&LH_PrefLoc=1&_sop=13"
    )


def card_number_match(title: str, number: str) -> float:
    number = normalize_text(number).replace(" ", "")
    if not number:
        return 0.0

    normal_title = normalize_text(title)
    title_compact = normal_title.replace(" ", "")
    escaped = re.escape(number)

    if re.search(
        rf"(?<![a-z0-9]){escaped}(?:/\d+)?(?![a-z0-9])",
        normal_title,
    ):
        return 1.0
    if number in title_compact:
        return 0.75
    return 0.0


def listing_match_score(
    candidate: Candidate,
    listing_title: str,
    exclusions: Iterable[str],
) -> tuple[float, str]:
    title_normalized = normalize_text(listing_title)
    title_tokens = set(title_normalized.split())

    for excluded in exclusions:
        term = normalize_text(excluded)
        if term and term in title_normalized:
            return 0.0, f"Excluded term: {excluded}"

    name_tokens = meaningful_tokens(candidate.name)
    name_hits = sum(token in title_tokens for token in name_tokens)
    name_score = (
        name_hits / len(name_tokens)
        if name_tokens
        else 0.0
    )

    number_score = card_number_match(
        listing_title,
        candidate.number,
    )

    set_tokens = meaningful_tokens(candidate.set_name)
    set_hits = sum(token in title_tokens for token in set_tokens)
    set_score = (
        set_hits / len(set_tokens)
        if set_tokens
        else 0.0
    )

    variant = normalize_text(candidate.variant)
    variant_score = 0.50
    if "reverse" in variant:
        variant_score = (
            1.0 if "reverse" in title_normalized else 0.10
        )
    elif "holo" in variant:
        if "reverse" in title_normalized:
            variant_score = 0.20
        elif (
            "holo" in title_normalized
            or "foil" in title_normalized
        ):
            variant_score = 1.0
        else:
            variant_score = 0.55
    elif variant == "normal":
        variant_score = (
            0.35
            if (
                "reverse" in title_normalized
                or "holo" in title_normalized
            )
            else 0.75
        )
    elif "1st" in variant or "first" in variant:
        variant_score = (
            1.0
            if (
                "1st" in title_normalized
                or "first" in title_normalized
            )
            else 0.15
        )

    score = (
        0.47 * name_score
        + 0.30 * number_score
        + 0.12 * set_score
        + 0.11 * variant_score
    )

    if name_score < 0.60:
        return 0.0, "Card name did not match reliably"
    if number_score < 0.75:
        return 0.0, "Exact card number was not found"
    if set_score == 0:
        score *= 0.88

    return min(1.0, score), ""


def confidence_label(score: float) -> str:
    if score >= 0.84:
        return "High"
    if score >= 0.72:
        return "Medium"
    return "Low"


class CandidateTitleMatcher:
    """Match an unknown auction title to one exact market-database variant."""

    def __init__(self, candidates: Iterable[Candidate]) -> None:
        from collections import defaultdict

        self._token_index: dict[str, list[Candidate]] = defaultdict(list)
        for candidate in candidates:
            for token in set(meaningful_tokens(candidate.name)):
                if len(token) >= 3:
                    self._token_index[token].append(candidate)

    def match(
        self,
        title: str,
        exclusions: Iterable[str],
    ) -> tuple[Candidate | None, float, str]:
        normalized = normalize_text(title)
        title_tokens = set(normalized.split())
        candidate_pool: dict[str, Candidate] = {}

        for token in title_tokens:
            for candidate in self._token_index.get(token, []):
                candidate_pool[candidate.identity] = candidate

        scored: list[tuple[float, Candidate]] = []
        for candidate in candidate_pool.values():
            score, _ = listing_match_score(
                candidate,
                title,
                exclusions,
            )
            if score >= 0.72:
                scored.append((score, candidate))

        if not scored:
            return None, 0.0, "No exact database card match"

        scored.sort(
            key=lambda value: (
                value[0],
                value[1].market_value,
            ),
            reverse=True,
        )
        best_score, best = scored[0]

        if len(scored) > 1:
            second_score, second = scored[1]
            if (
                best.identity != second.identity
                and best_score - second_score < 0.045
            ):
                return (
                    None,
                    best_score,
                    "Ambiguous database match",
                )

        return best, best_score, ""


def decision_for(
    ratio: float,
    match_score: float,
    feedback_percent: float,
    feedback_count: int,
    settings: RadarSettings,
    headroom: float,
) -> str:
    seller_ok = (
        feedback_percent >= settings.minimum_feedback
        and feedback_count >= settings.minimum_feedback_count
    )

    if (
        ratio <= settings.target_ratio
        and match_score >= 0.72
        and seller_ok
        and headroom >= 0
    ):
        return "GREEN"

    if (
        ratio <= settings.amber_upper_ratio
        and match_score >= 0.68
        and feedback_percent >= max(
            95.0,
            settings.minimum_feedback - 2,
        )
    ):
        return "AMBER"

    return "RED"


def score_listing(
    ratio: float,
    match_score: float,
    feedback_percent: float,
    minutes_remaining: int,
    bid_count: int,
    target_ratio: float,
) -> float:
    discount = max(
        0.0,
        min(45.0, (1.0 - ratio) * 100 * 1.5),
    )
    match = match_score * 28
    feedback = max(
        0.0,
        min(10.0, feedback_percent - 90),
    )

    if minutes_remaining <= 5:
        urgency = 15.0
    elif minutes_remaining <= 15:
        urgency = 13.0
    elif minutes_remaining <= 60:
        urgency = 10.0
    elif minutes_remaining <= 360:
        urgency = 7.0
    else:
        urgency = 4.0

    competition = max(
        0.0,
        5.0 - min(bid_count, 10) * 0.5,
    )
    target_bonus = 5.0 if ratio <= target_ratio else 0.0

    return round(
        min(
            100.0,
            discount
            + match
            + feedback
            + urgency
            + competition
            + target_bonus,
        ),
        1,
    )


def within_time_window(
    minutes_remaining: int,
    settings: RadarSettings,
) -> bool:
    return (
        minutes_remaining >= settings.minimum_minutes_remaining
        and minutes_remaining
        <= settings.maximum_hours_remaining * 60
    )
