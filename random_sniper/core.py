from __future__ import annotations

import math
import random
import re
import unicodedata
from dataclasses import dataclass, field
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
    release_date: Any = None
    image_url: str = ""
    price_change: float = 0.0
    historical_scans: int = 0
    historical_green: int = 0
    last_selected: datetime | None = None

    @property
    def identity(self) -> str:
        base = self.card_id or (
            f"{self.name}|{self.set_name}|{self.number}"
        )
        return f"{base}|{self.variant}".casefold()

    @property
    def card_identity(self) -> str:
        return (
            self.card_id
            or f"{self.name}|{self.set_name}|{self.number}"
        ).casefold()


@dataclass
class Settings:
    minimum_value: float = 5.0
    maximum_value: float = 40.0
    number_of_cards: int = 20
    selection_mode: str = "Smart Random"
    category: str = "Pokémon only"
    variant_filter: str = "Any"
    one_variant_per_card: bool = True
    cooldown_days: int = 14
    replace_no_results: bool = True
    search_depth: str = "Balanced"
    target_ratio: float = 0.75
    ending_within_hours: float = 24.0
    minimum_feedback: float = 98.0
    maximum_postage: float | None = None
    copy_green_to_main_queue: bool = True
    maximum_attempts: int = 60
    random_seed: str = ""


@dataclass
class ListingResult:
    candidate: Candidate
    title: str
    item_id: str
    item_url: str
    image_url: str
    current_bid: float
    postage: float
    delivered: float
    market_value: float
    ratio: float
    target_delivered: float
    maximum_bid: float
    headroom: float
    end_time: datetime
    minutes_remaining: int
    within_sniping_window: bool
    bid_count: int
    seller: str
    feedback_percent: float
    feedback_count: int
    condition: str
    match_score: float
    match_confidence: str
    search_query: str
    active_search_url: str
    sold_search_url: str
    score: float
    decision: str
    notes: str = ""


def normalize_card_number(value: Any) -> str:
    """Convert Excel whole-number values such as 54.0 back to '54'.

    Text identifiers such as RC10, TG06, 58/102 and leading-zero strings are
    preserved exactly.
    """
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
    if not text:
        return ""

    # Excel/COM can occasionally expose an integral cell as the string "54.0".
    match = re.fullmatch(r"([+-]?\d+)\.0+", text)
    if match:
        return match.group(1)

    return text


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def meaningful_tokens(value: str) -> list[str]:
    ignored = {
        "pokemon", "card", "cards", "tcg", "the", "and", "of", "set",
        "edition", "rare", "trading", "game",
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
    if "1st" in value and "holo" in value:
        return "1st edition holo"
    if "1st" in value:
        return "1st edition"
    if "holo" in value:
        return "holo"
    return variant


def build_queries(candidate: Candidate, search_depth: str) -> list[str]:
    variant = variant_keywords(candidate.variant)
    components = {
        "name": candidate.name,
        "set": candidate.set_name,
        "number": candidate.number,
        "variant": variant,
    }

    templates = [
        "{name} {set} {number} {variant}",
    ]
    if search_depth in {"Balanced", "Deep"}:
        templates.append("{name} {number} {variant}")
    if search_depth == "Deep":
        templates.append("{name} {set} {variant}")

    queries: list[str] = []
    for template in templates:
        query = template.format(**components)
        query = re.sub(r"\s+", " ", query).strip()
        if query and query.casefold() not in {item.casefold() for item in queries}:
            queries.append(query)
    return queries


def ebay_active_search_url(query: str) -> str:
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


def parse_percentage(value: Any, default: float) -> float:
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number <= 1 else number / 100
    text = str(value).strip().replace("%", "")
    try:
        return float(text) / 100
    except ValueError:
        return default


def parse_currency_or_any(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.casefold() == "any":
        return None
    text = text.replace("£", "").replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def parse_duration_hours(value: Any, default: float = 24.0) -> float:
    text = str(value or "").strip().casefold()
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return default
    number = float(match.group(1))
    if "minute" in text:
        return number / 60
    if "day" in text:
        return number * 24
    return number


def parse_cooldown_days(value: Any) -> int:
    text = str(value or "").strip().casefold()
    if text in {"", "no cooldown", "none"}:
        return 0
    if "pool exhausted" in text:
        return 36500
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def candidate_matches_category(candidate: Candidate, category: str) -> bool:
    category_normalized = normalize_text(category)
    supertype = normalize_text(candidate.supertype)

    if category_normalized in {"all cards", "all"}:
        return True
    if "pokemon trainer" in category_normalized:
        return supertype in {"pokemon", "trainer"}
    if "pokemon" in category_normalized:
        return supertype == "pokemon"
    if "trainer" in category_normalized:
        return supertype == "trainer"
    if "energy" in category_normalized:
        return supertype == "energy"
    return True


def candidate_matches_variant(candidate: Candidate, variant_filter: str) -> bool:
    wanted = normalize_text(variant_filter)
    actual = normalize_text(candidate.variant)

    if wanted in {"", "any", "all variants"}:
        return True
    if wanted == "normal":
        return actual == "normal"
    if wanted == "holo":
        return "holo" in actual and "reverse" not in actual
    if wanted == "reverse holo":
        return "reverse" in actual
    if wanted == "first edition":
        return "1st" in actual or "first" in actual
    return wanted in actual


def release_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.year
    if isinstance(value, (int, float)):
        # Excel's 1900 date system uses 1899-12-30 as the practical origin.
        try:
            from datetime import timedelta
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).year
        except (OverflowError, TypeError, ValueError):
            return None
    text = str(value)
    match = re.search(r"(19|20)\d{2}", text)
    return int(match.group(0)) if match else None


def eligible_candidates(
    candidates: Iterable[Candidate],
    settings: Settings,
    now: datetime,
    vintage_cutoff_year: int,
    modern_start_year: int,
) -> list[Candidate]:
    output: list[Candidate] = []

    for candidate in candidates:
        if not (
            settings.minimum_value
            <= candidate.market_value
            <= settings.maximum_value
        ):
            continue
        if not candidate_matches_category(candidate, settings.category):
            continue
        if not candidate_matches_variant(candidate, settings.variant_filter):
            continue

        if settings.cooldown_days and candidate.last_selected:
            age_days = (now - candidate.last_selected).total_seconds() / 86400
            if age_days < settings.cooldown_days:
                continue

        year = release_year(candidate.release_date)
        if settings.selection_mode == "Vintage Random":
            if year is None or year > vintage_cutoff_year:
                continue
        elif settings.selection_mode == "Modern Random":
            if year is None or year < modern_start_year:
                continue

        output.append(candidate)

    return output


def _dedupe_cards(
    values: list[Candidate],
    one_variant_per_card: bool,
) -> list[Candidate]:
    if not one_variant_per_card:
        return values

    seen: set[str] = set()
    output: list[Candidate] = []
    for candidate in values:
        if candidate.card_identity in seen:
            continue
        seen.add(candidate.card_identity)
        output.append(candidate)
    return output


def _smart_random(
    candidates: list[Candidate],
    count: int,
    rng: random.Random,
    minimum: float,
    maximum: float,
) -> list[Candidate]:
    if count <= 0 or not candidates:
        return []

    band_count = min(5, count)
    width = max((maximum - minimum) / band_count, 0.01)
    bands: list[list[Candidate]] = [[] for _ in range(band_count)]

    for candidate in candidates:
        index = min(
            band_count - 1,
            int((candidate.market_value - minimum) / width),
        )
        bands[index].append(candidate)

    for band in bands:
        rng.shuffle(band)

    selected: list[Candidate] = []
    while len(selected) < count:
        progress = False
        for band in bands:
            if band and len(selected) < count:
                selected.append(band.pop())
                progress = True
        if not progress:
            break

    if len(selected) < count:
        remaining = [
            item for band in bands for item in band
            if item.identity not in {value.identity for value in selected}
        ]
        rng.shuffle(remaining)
        selected.extend(remaining[: count - len(selected)])

    return selected[:count]


def select_candidates(
    candidates: list[Candidate],
    settings: Settings,
    count: int | None = None,
    exclude_identities: set[str] | None = None,
) -> list[Candidate]:
    desired = count if count is not None else settings.number_of_cards
    excluded = exclude_identities or set()
    pool = [
        candidate
        for candidate in candidates
        if candidate.identity not in excluded
    ]

    seed = settings.random_seed or datetime.now(timezone.utc).isoformat()
    rng = random.Random(seed)

    mode = settings.selection_mode
    if mode == "Never Scanned First":
        pool.sort(key=lambda item: (item.historical_scans, rng.random()))
    elif mode == "Previously Successful":
        pool.sort(
            key=lambda item: (
                -item.historical_green,
                item.historical_scans,
                rng.random(),
            )
        )
    elif mode == "Rising Market":
        pool.sort(
            key=lambda item: (
                -item.price_change,
                item.historical_scans,
                rng.random(),
            )
        )
    else:
        rng.shuffle(pool)

    pool = _dedupe_cards(pool, settings.one_variant_per_card)

    if mode == "Smart Random":
        return _smart_random(
            pool,
            desired,
            rng,
            settings.minimum_value,
            settings.maximum_value,
        )

    return pool[:desired]


def card_number_match(title: str, number: str) -> float:
    number = normalize_text(number).replace(" ", "")
    if not number:
        return 0.0

    title_compact = normalize_text(title).replace(" ", "")
    escaped = re.escape(number)
    if re.search(rf"(?<![a-z0-9]){escaped}(?:/\d+)?(?![a-z0-9])", normalize_text(title)):
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

    for excluded in exclusions:
        excluded_normalized = normalize_text(excluded)
        if excluded_normalized and excluded_normalized in title_normalized:
            return 0.0, f"Excluded term: {excluded}"

    name_tokens = meaningful_tokens(candidate.name)
    name_hits = sum(
        1 for token in name_tokens if token in title_normalized.split()
    )
    name_score = (
        name_hits / len(name_tokens)
        if name_tokens
        else 0.0
    )

    number_score = card_number_match(listing_title, candidate.number)

    set_tokens = meaningful_tokens(candidate.set_name)
    set_hits = sum(
        1 for token in set_tokens if token in title_normalized.split()
    )
    set_score = (
        set_hits / len(set_tokens)
        if set_tokens
        else 0.0
    )

    variant = normalize_text(candidate.variant)
    variant_score = 0.5
    if "reverse" in variant:
        variant_score = 1.0 if "reverse" in title_normalized else 0.1
    elif "holo" in variant:
        if "reverse" in title_normalized:
            variant_score = 0.2
        elif "holo" in title_normalized or "foil" in title_normalized:
            variant_score = 1.0
        else:
            variant_score = 0.55
    elif variant == "normal":
        variant_score = (
            0.35
            if ("reverse" in title_normalized or "holo" in title_normalized)
            else 0.75
        )
    elif "1st" in variant or "first" in variant:
        variant_score = (
            1.0
            if ("1st" in title_normalized or "first" in title_normalized)
            else 0.15
        )

    score = (
        0.48 * name_score
        + 0.27 * number_score
        + 0.10 * set_score
        + 0.15 * variant_score
    )

    # Card-name presence is mandatory. For purely numeric card numbers, set
    # or variant evidence is especially valuable.
    if name_score < 0.60:
        return 0.0, "Card name did not match reliably"
    if number_score == 0 and set_score < 0.45:
        score *= 0.70

    return min(1.0, score), ""


def confidence_label(score: float) -> str:
    if score >= 0.82:
        return "High"
    if score >= 0.64:
        return "Medium"
    return "Low"


def score_listing(
    ratio: float,
    match_score: float,
    feedback_percent: float,
    minutes_remaining: int,
    bid_count: int,
    target_ratio: float,
) -> float:
    discount_component = max(
        0.0,
        min(45.0, (1.0 - ratio) * 100 * 1.5),
    )
    match_component = match_score * 30
    feedback_component = max(
        0.0,
        min(10.0, (feedback_percent - 90) / 1.0),
    )
    urgency_component = 10.0 if minutes_remaining <= 60 else (
        7.0 if minutes_remaining <= 360 else 4.0
    )
    competition_component = max(0.0, 5.0 - min(bid_count, 10) * 0.5)

    # Give a small bonus for being within the configured purchase target.
    target_bonus = 5.0 if ratio <= target_ratio else 0.0

    return round(
        min(
            100.0,
            discount_component
            + match_component
            + feedback_component
            + urgency_component
            + competition_component
            + target_bonus,
        ),
        1,
    )


def decision_for(
    ratio: float,
    match_score: float,
    feedback_percent: float,
    minimum_feedback: float,
    target_ratio: float,
    headroom: float,
) -> str:
    if (
        ratio <= target_ratio
        and match_score >= 0.72
        and feedback_percent >= minimum_feedback
        and headroom >= 0
    ):
        return "GREEN"

    if (
        ratio <= min(0.90, target_ratio + 0.15)
        and match_score >= 0.56
        and feedback_percent >= max(95.0, minimum_feedback - 2)
    ):
        return "AMBER"

    return "RED"
