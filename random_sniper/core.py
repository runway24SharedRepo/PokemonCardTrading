from __future__ import annotations

import math
import random
import re
import unicodedata
from dataclasses import dataclass, field
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
    listing_formats: str = "Auctions + Buy It Now"
    expand_green_sellers: bool = True
    maximum_green_sellers: int = 5
    seller_item_scan_limit: int = 100
    maximum_seller_opportunities: int = 5


@dataclass
class ListingResult:
    candidate: Candidate
    title: str
    item_id: str
    item_url: str
    image_url: str
    buying_options: tuple[str, ...]
    listing_type: str
    current_bid: float | None
    buy_now_price: float | None
    postage: float
    bid_delivered: float | None
    buy_now_delivered: float | None
    market_value: float
    bid_ratio: float | None
    buy_now_ratio: float | None
    target_delivered: float
    maximum_bid: float | None
    bid_headroom: float | None
    buy_now_headroom: float | None
    bid_decision: str
    buy_now_decision: str
    recommended_action: str
    end_time: datetime
    minutes_remaining: int
    within_sniping_window: bool
    queue_eligible: bool
    bid_count: int
    seller: str
    feedback_percent: float
    feedback_count: int
    condition: str
    match_score: float
    match_confidence: str
    search_query: str
    auction_search_url: str
    buy_now_search_url: str
    sold_search_url: str
    score: float
    decision: str
    condition_flag: str = "AMBER"
    condition_details: str = ""
    discovery_source: str = "RANDOM SEARCH"
    parent_item_id: str = ""
    seller_group: str = ""
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
    def delivered(self) -> float | None:
        values = [
            value for value in (self.bid_delivered, self.buy_now_delivered)
            if value is not None
        ]
        return min(values) if values else None

    @property
    def ratio(self) -> float:
        values = [
            value for value in (self.bid_ratio, self.buy_now_ratio)
            if value is not None
        ]
        return min(values) if values else 999.0

    @property
    def headroom(self) -> float | None:
        if self.recommended_action in {"BUY NOW", "BID OR BUY NOW"}:
            return self.buy_now_headroom
        return self.bid_headroom


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


def ebay_auction_search_url(query: str) -> str:
    return (
        "https://www.ebay.co.uk/sch/i.html?"
        f"_nkw={quote_plus(query)}"
        "&_sacat=0&LH_Auction=1&LH_PrefLoc=1&_sop=1"
    )


def ebay_buy_now_search_url(query: str) -> str:
    return (
        "https://www.ebay.co.uk/sch/i.html?"
        f"_nkw={quote_plus(query)}"
        "&_sacat=0&LH_BIN=1&LH_PrefLoc=1&_sop=15"
    )


def ebay_active_search_url(query: str) -> str:
    """Backward-compatible alias for the auction search URL."""
    return ebay_auction_search_url(query)


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
        return actual in {
            "normal",
            "unlimited",
            "unlimited normal",
            "standard",
        }
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
    *,
    ignore_market_value: bool = False,
) -> list[Candidate]:
    output: list[Candidate] = []

    for candidate in candidates:
        if not ignore_market_value and not (
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

    positions: dict[str, int] = {}
    output: list[Candidate] = []

    for candidate in values:
        key = candidate.card_identity
        if key not in positions:
            positions[key] = len(output)
            output.append(candidate)
            continue

        old_position = positions[key]
        old = output[old_position]

        # Never retain an accidental First Edition selection when a standard
        # variant of the same exact card is available.
        if (
            is_first_edition_variant(old.variant)
            and not is_first_edition_variant(candidate.variant)
        ):
            output[old_position] = candidate

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


_DECISION_RANK = {"N/A": -1, "RED": 0, "AMBER": 1, "GREEN": 2}


def overall_decision(bid_decision: str, buy_now_decision: str) -> str:
    return max(
        (bid_decision, buy_now_decision),
        key=lambda value: _DECISION_RANK.get(value, -1),
    )


def recommended_action(
    bid_decision: str,
    buy_now_decision: str,
    within_sniping_window: bool,
) -> str:
    if bid_decision == "GREEN" and buy_now_decision == "GREEN":
        return "BID OR BUY NOW" if within_sniping_window else "BUY NOW / WATCH BID"
    if buy_now_decision == "GREEN":
        return "BUY NOW"
    if bid_decision == "GREEN":
        return "BID / SNIPE" if within_sniping_window else "WATCH AUCTION"
    if buy_now_decision == "AMBER" and bid_decision == "AMBER":
        return "REVIEW BOTH"
    if buy_now_decision == "AMBER":
        return "REVIEW BUY NOW"
    if bid_decision == "AMBER":
        return "WATCH AUCTION"
    return "SKIP"
