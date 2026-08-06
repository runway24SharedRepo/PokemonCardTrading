from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import quote_plus

from edition_safety import (
    edition_conflict,
    edition_variant_score,
    is_first_edition_variant,
)


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
    release_date: Any = None
    image_url: str = ""
    price_change: float = 0.0

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
    long_term_score: int = 0
    investment_tier: str = ""
    long_term_action: str = ""
    demand_score: int = 0
    scarcity_score: int = 0
    significance_score: int = 0
    reprint_resistance_score: int = 0
    condition_investment_score: int = 0
    price_resilience_score: int = 0
    acquisition_discount_score: int = 0
    investment_data_confidence: str = ""
    portfolio_fit: str = ""
    minimum_hold_years: int = 0
    investment_thesis: str = ""
    investment_risks: str = ""
    desired_max_ratio: float | None = None

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



_COLLECTOR_FRACTION_RE = re.compile(
    r"(?<![a-z0-9])"
    r"([a-z]{0,6}-?\d{1,4})"
    r"\s*/\s*"
    r"([a-z]{0,6}-?\d{1,4})"
    r"(?![a-z0-9])",
    re.IGNORECASE,
)

_PRIMARY_CARD_FORMS = {
    "v",
    "vmax",
    "vstar",
    "ex",
    "gx",
    "break",
    "prime",
    "lvx",
    "vunion",
    "mega",
}
_CARD_NAME_MODIFIERS = {
    "dark",
    "light",
    "radiant",
    "shining",
}
_INDEX_NOISE_TOKENS = {
    "ex",
    "gx",
    "vmax",
    "vstar",
    "break",
    "prime",
    "holo",
    "foil",
}


def _plain_text(value: Any) -> str:
    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    return "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    ).casefold()


def canonical_collector_token(value: Any) -> str:
    """Canonicalise one collector-number component.

    Numeric leading zeroes are ignored, so 028 and 28 represent the same
    printed number. Alphanumeric promo/subset identifiers retain their prefix,
    so XY41, TG06 and SWSH020 remain distinct identities.
    """

    compact = re.sub(
        r"[^a-z0-9]+",
        "",
        _plain_text(value),
    )
    if not compact:
        return ""

    match = re.fullmatch(
        r"([a-z]*)(\d+)",
        compact,
    )
    if not match:
        return compact

    prefix, digits = match.groups()
    return f"{prefix}{int(digits)}"


def _candidate_collector_parts(
    number: Any,
) -> tuple[str, str]:
    raw = _plain_text(number).strip()
    if not raw:
        return "", ""

    pieces = raw.split("/", 1)
    numerator = canonical_collector_token(
        pieces[0]
    )
    denominator = (
        canonical_collector_token(pieces[1])
        if len(pieces) > 1
        else ""
    )
    return numerator, denominator


def _title_collector_fractions(
    title: Any,
) -> list[tuple[str, str, str]]:
    raw = _plain_text(title).replace("／", "/")
    output: list[tuple[str, str, str]] = []

    for match in _COLLECTOR_FRACTION_RE.finditer(raw):
        numerator = canonical_collector_token(
            match.group(1)
        )
        denominator = canonical_collector_token(
            match.group(2)
        )
        if numerator and denominator:
            output.append(
                (
                    numerator,
                    denominator,
                    match.group(0).strip(),
                )
            )
    return output


def collector_number_evidence(
    title: Any,
    number: Any,
) -> tuple[float, bool, str]:
    """Return score, hard-conflict flag and diagnostic text.

    When a listing contains an explicit printed fraction such as 028/88,
    only the numerator may identify the card. A different numerator is a hard
    identity conflict; the denominator can never match candidate number 88.
    """

    expected, expected_total = (
        _candidate_collector_parts(number)
    )
    if not expected:
        return 0.0, False, (
            "The market database has no collector number"
        )

    fractions = _title_collector_fractions(title)
    if fractions:
        for numerator, denominator, _ in fractions:
            if numerator != expected:
                continue
            if (
                expected_total
                and denominator != expected_total
            ):
                continue
            return 1.0, False, ""

        observed = ", ".join(
            original
            for _, _, original in fractions[:3]
        )
        return (
            0.0,
            True,
            (
                f"Collector-number conflict: listing shows "
                f"{observed}; expected {number}"
            ),
        )

    raw = _plain_text(title)

    # Strong evidence when the seller explicitly labels the number.
    labelled_pattern = re.compile(
        rf"(?:#|no\.?|number)\s*0*"
        rf"{re.escape(expected)}"
        rf"(?![a-z0-9])",
        re.IGNORECASE,
    )
    if labelled_pattern.search(raw):
        return 0.95, False, ""

    # Exact standalone token. This also handles compact promo numbers such as
    # XY41 and leading-zero numeric titles such as 028.
    for token in re.findall(
        r"[a-z]*\d+|\d+[a-z]*",
        raw,
        flags=re.IGNORECASE,
    ):
        if canonical_collector_token(token) == expected:
            return 0.82, False, ""

    return (
        0.0,
        False,
        (
            f"Exact collector number {number} "
            "was not found in the listing title"
        ),
    )


def _extract_card_forms(
    tokens: list[str],
) -> set[str]:
    forms: set[str] = set()
    token_set = set(tokens)

    if "vstar" in token_set:
        forms.add("vstar")
    elif "vmax" in token_set:
        forms.add("vmax")
    elif (
        "v" in token_set
        and "union" in token_set
    ):
        forms.add("vunion")
    elif "vunion" in token_set:
        forms.add("vunion")
    elif "v" in token_set:
        forms.add("v")

    for value in (
        "ex",
        "gx",
        "break",
        "prime",
    ):
        if value in token_set:
            forms.add(value)

    if (
        "lvx" in token_set
        or (
            "lv" in token_set
            and "x" in token_set
        )
        or (
            "level" in token_set
            and "x" in token_set
        )
    ):
        forms.add("lvx")

    if (
        "mega" in token_set
        or (
            "m" in token_set
            and "ex" in token_set
        )
    ):
        forms.add("mega")

    for value in _CARD_NAME_MODIFIERS:
        if value in token_set:
            forms.add(value)

    return forms


def _base_name_tokens(
    candidate_name: str,
) -> list[str]:
    tokens = normalize_text(candidate_name).split()
    removable = {
        "v",
        "vmax",
        "vstar",
        "ex",
        "gx",
        "break",
        "prime",
        "lv",
        "level",
        "x",
        "lvx",
        "union",
        "vunion",
        "mega",
        "m",
        *_CARD_NAME_MODIFIERS,
    }
    base = [
        token
        for token in tokens
        if token not in removable
    ]
    return base or tokens


def card_form_conflict(
    candidate_name: str,
    listing_title: str,
) -> str:
    """Reject different Pokémon card forms near the detected card name."""

    candidate_tokens = normalize_text(
        candidate_name
    ).split()
    candidate_forms = _extract_card_forms(
        candidate_tokens
    )

    base_tokens = _base_name_tokens(candidate_name)
    title_tokens = normalize_text(
        listing_title
    ).split()

    anchor = -1
    for base_token in base_tokens:
        try:
            anchor = title_tokens.index(base_token)
            break
        except ValueError:
            continue

    if anchor < 0:
        return ""

    # Forms in card titles normally occur immediately before or shortly after
    # the Pokémon name: M Charizard EX, Mawile VSTAR, Garchomp C LV.X.
    window = title_tokens[
        max(0, anchor - 2):
        min(len(title_tokens), anchor + len(base_tokens) + 4)
    ]
    title_forms = _extract_card_forms(window)

    candidate_primary = (
        candidate_forms & _PRIMARY_CARD_FORMS
    )
    title_primary = title_forms & _PRIMARY_CARD_FORMS

    if (
        candidate_primary != title_primary
        and (candidate_primary or title_primary)
    ):
        expected = (
            "/".join(sorted(candidate_primary))
            if candidate_primary
            else "standard card"
        )
        observed = (
            "/".join(sorted(title_primary))
            if title_primary
            else "standard card"
        )
        return (
            "Card-form conflict: listing appears to be "
            f"{observed}; database candidate is {expected}"
        )

    candidate_modifiers = (
        candidate_forms & _CARD_NAME_MODIFIERS
    )
    title_modifiers = (
        title_forms & _CARD_NAME_MODIFIERS
    )
    if (
        candidate_modifiers != title_modifiers
        and (
            candidate_modifiers
            or title_modifiers
        )
    ):
        expected = (
            "/".join(sorted(candidate_modifiers))
            if candidate_modifiers
            else "unmodified"
        )
        observed = (
            "/".join(sorted(title_modifiers))
            if title_modifiers
            else "unmodified"
        )
        return (
            "Card-name modifier conflict: listing is "
            f"{observed}; database candidate is {expected}"
        )

    return ""


def explicit_variant_conflict(
    candidate_variant: str,
    listing_title: str,
) -> str:
    title = normalize_text(listing_title)
    variant = normalize_text(candidate_variant)

    title_reverse = (
        "reverse holo" in title
        or "reverse foil" in title
        or "rev holo" in title
    )
    candidate_reverse = "reverse" in variant

    if title_reverse and not candidate_reverse:
        return (
            "Variant conflict: listing explicitly says "
            "Reverse Holo"
        )

    if candidate_reverse and (
        "regular holo" in title
        or "normal holo" in title
        or "non reverse" in title
        or "non reverse holo" in title
    ):
        return (
            "Variant conflict: listing explicitly identifies "
            "a regular/non-Reverse version"
        )

    hard_edition_conflict = edition_conflict(
        candidate_variant,
        listing_title,
    )
    if hard_edition_conflict:
        return hard_edition_conflict

    return ""

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
    score, _, _ = collector_number_evidence(
        title,
        number,
    )
    return score

def listing_match_score(
    candidate: Candidate,
    listing_title: str,
    exclusions: Iterable[str],
) -> tuple[float, str]:
    title_normalized = normalize_text(listing_title)
    title_tokens = set(title_normalized.split())

    for excluded in exclusions:
        excluded_normalized = normalize_text(excluded)
        if (
            excluded_normalized
            and excluded_normalized in title_normalized
        ):
            return 0.0, f"Excluded term: {excluded}"

    name_tokens = meaningful_tokens(candidate.name)
    name_hits = sum(
        1
        for token in name_tokens
        if token in title_tokens
    )
    name_score = (
        name_hits / len(name_tokens)
        if name_tokens
        else 0.0
    )
    if name_score < 0.72:
        return 0.0, (
            "Card name did not match reliably"
        )

    form_conflict = card_form_conflict(
        candidate.name,
        listing_title,
    )
    if form_conflict:
        return 0.0, form_conflict

    number_score, hard_conflict, number_reason = (
        collector_number_evidence(
            listing_title,
            candidate.number,
        )
    )
    if hard_conflict:
        return 0.0, number_reason
    if number_score < 0.75:
        return 0.0, number_reason

    variant_conflict = explicit_variant_conflict(
        candidate.variant,
        listing_title,
    )
    if variant_conflict:
        return 0.0, variant_conflict

    set_tokens = meaningful_tokens(candidate.set_name)
    set_hits = sum(
        1
        for token in set_tokens
        if token in title_tokens
    )
    set_score = (
        set_hits / len(set_tokens)
        if set_tokens
        else 0.0
    )
    normalized_set = normalize_text(
        candidate.set_name
    )
    if (
        normalized_set
        and normalized_set in title_normalized
    ):
        set_score = 1.0

    variant = normalize_text(candidate.variant)
    edition_score = edition_variant_score(
        candidate.variant,
        listing_title,
    )

    if edition_score is not None:
        variant_score = edition_score
    elif "reverse" in variant:
        variant_score = (
            1.0
            if (
                "reverse holo" in title_normalized
                or "reverse foil" in title_normalized
                or "rev holo" in title_normalized
            )
            else 0.15
        )
    elif "holo" in variant:
        if "reverse" in title_normalized:
            variant_score = 0.10
        elif (
            "holo" in title_normalized
            or "foil" in title_normalized
        ):
            variant_score = 1.0
        else:
            variant_score = 0.55
    elif variant in {
        "normal",
        "unlimited",
        "unlimited normal",
        "standard",
    }:
        variant_score = (
            0.30
            if (
                "reverse" in title_normalized
                or "holo" in title_normalized
                or "foil" in title_normalized
            )
            else 0.82
        )
    else:
        variant_score = 0.50


    score = (
        0.45 * name_score
        + 0.32 * number_score
        + 0.13 * set_score
        + 0.10 * variant_score
    )

    # Titles without a set name can still be accepted when name, form and
    # printed number uniquely identify the candidate. Ambiguity is handled by
    # CandidateTitleMatcher against the complete market database.
    if set_score == 0:
        score *= 0.94

    return min(1.0, score), ""

def confidence_label(score: float) -> str:
    if score >= 0.84:
        return "High"
    if score >= 0.72:
        return "Medium"
    return "Low"


class CandidateTitleMatcher:
    """Match an unknown listing to one unambiguous database identity."""

    def __init__(
        self,
        candidates: Iterable[Candidate],
    ) -> None:
        from collections import defaultdict

        self._token_index: dict[
            str,
            list[Candidate],
        ] = defaultdict(list)

        for candidate in candidates:
            for token in set(
                meaningful_tokens(candidate.name)
            ):
                if (
                    len(token) >= 2
                    and token not in {
                        "ex",
                        "gx",
                        "vmax",
                        "vstar",
                        "break",
                        "prime",
                    }
                ):
                    self._token_index[token].append(
                        candidate
                    )

    def match(
        self,
        title: str,
        exclusions: Iterable[str],
    ) -> tuple[
        Candidate | None,
        float,
        str,
    ]:
        normalized = normalize_text(title)
        title_tokens = set(normalized.split())
        candidate_pool: dict[
            str,
            Candidate,
        ] = {}

        for token in title_tokens:
            for candidate in self._token_index.get(
                token,
                [],
            ):
                candidate_pool[
                    candidate.identity
                ] = candidate

        scored: list[
            tuple[float, float, Candidate]
        ] = []
        for candidate in candidate_pool.values():
            score, _ = listing_match_score(
                candidate,
                title,
                exclusions,
            )
            if score < 0.72:
                continue

            set_tokens = meaningful_tokens(
                candidate.set_name
            )
            set_score = (
                sum(
                    token in title_tokens
                    for token in set_tokens
                )
                / len(set_tokens)
                if set_tokens
                else 0.0
            )
            scored.append(
                (
                    score,
                    set_score,
                    candidate,
                )
            )

        if not scored:
            return (
                None,
                0.0,
                "No exact database card match",
            )

        scored.sort(
            key=lambda value: (
                value[0],
                value[1],
                value[2].market_value,
            ),
            reverse=True,
        )
        best_score, best_set_score, best = scored[0]

        if len(scored) > 1:
            (
                second_score,
                second_set_score,
                second,
            ) = scored[1]

            clear_set_advantage = (
                best_set_score >= 0.75
                and best_set_score
                - second_set_score >= 0.35
            )
            clear_score_advantage = (
                best_score - second_score >= 0.055
            )

            if (
                best.identity != second.identity
                and not clear_set_advantage
                and not clear_score_advantage
            ):
                return (
                    None,
                    best_score,
                    (
                        "Ambiguous exact identity: multiple "
                        "sets or variants remain possible"
                    ),
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
