from __future__ import annotations

import math
import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable


DEFAULT_ICONIC_POKEMON = (
    "Charizard", "Pikachu", "Eevee", "Mew", "Mewtwo", "Lugia",
    "Rayquaza", "Gengar", "Umbreon", "Espeon", "Sylveon",
    "Greninja", "Giratina", "Arceus", "Dragonite", "Blastoise",
    "Venusaur", "Snorlax", "Gyarados", "Lucario", "Gardevoir",
    "Magikarp", "Leafeon", "Glaceon", "Tyranitar", "Ho-Oh",
)


@dataclass
class InvestmentSettings:
    demand_weight: int = 25
    scarcity_weight: int = 20
    significance_weight: int = 15
    reprint_weight: int = 15
    condition_weight: int = 10
    resilience_weight: int = 10
    acquisition_weight: int = 5
    default_hold_years: int = 7
    core_asset_threshold: int = 90
    strong_buy_threshold: int = 80
    selective_buy_threshold: int = 70
    watch_threshold: int = 60
    max_same_card_quantity: int = 3
    max_same_pokemon_percent: float = 30.0
    iconic_pokemon: tuple[str, ...] = DEFAULT_ICONIC_POKEMON


@dataclass
class TargetOverride:
    enabled: bool = True
    card_id: str = ""
    name: str = ""
    set_name: str = ""
    number: str = ""
    variant: str = ""
    demand_score: float | None = None
    scarcity_score: float | None = None
    significance_score: float | None = None
    reprint_score: float | None = None
    total_score: float | None = None
    desired_max_ratio: float | None = None
    target_quantity: int | None = None
    minimum_hold_years: int | None = None
    thesis: str = ""
    risks: str = ""
    priority: str = ""
    notes: str = ""


@dataclass
class PriceHistoryStats:
    values: list[tuple[datetime, float]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def span_days(self) -> int:
        if len(self.values) < 2:
            return 0
        ordered = sorted(self.values, key=lambda item: item[0])
        return max(0, (ordered[-1][0] - ordered[0][0]).days)


@dataclass
class PortfolioHolding:
    card_key: str
    pokemon_key: str
    quantity: int
    cost: float
    current_value: float


@dataclass
class InvestmentContext:
    settings: InvestmentSettings = field(default_factory=InvestmentSettings)
    overrides: dict[str, TargetOverride] = field(default_factory=dict)
    history: dict[str, PriceHistoryStats] = field(default_factory=dict)
    portfolio_by_card: dict[str, PortfolioHolding] = field(default_factory=dict)
    portfolio_by_pokemon: dict[str, PortfolioHolding] = field(default_factory=dict)
    total_portfolio_value: float = 0.0


@dataclass
class InvestmentAssessment:
    long_term_score: int
    investment_tier: str
    long_term_action: str
    demand_score: int
    scarcity_score: int
    significance_score: int
    reprint_score: int
    condition_score: int
    resilience_score: int
    acquisition_score: int
    data_confidence: str
    portfolio_fit: str
    minimum_hold_years: int
    thesis: str
    risks: str
    desired_max_ratio: float | None = None


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.casefold().replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def card_key(candidate: Any) -> str:
    card_id = str(getattr(candidate, "card_id", "") or "").strip()
    if card_id:
        return card_id.casefold()
    return "|".join(
        normalize_text(value)
        for value in (
            getattr(candidate, "name", ""),
            getattr(candidate, "set_name", ""),
            getattr(candidate, "number", ""),
            getattr(candidate, "variant", ""),
        )
    )


def pokemon_key(name: Any) -> str:
    text = normalize_text(name)
    suffixes = {
        "ex", "gx", "v", "vmax", "vstar", "break", "lv", "x",
        "star", "radiant", "mega", "prism",
    }
    tokens = [token for token in text.split() if token not in suffixes]
    return " ".join(tokens) or text


def override_keys(candidate: Any) -> list[str]:
    keys = [card_key(candidate)]
    keys.append(
        "|".join(
            normalize_text(value)
            for value in (
                getattr(candidate, "name", ""),
                getattr(candidate, "set_name", ""),
                getattr(candidate, "number", ""),
                getattr(candidate, "variant", ""),
            )
        )
    )
    keys.append(
        "|".join(
            normalize_text(value)
            for value in (
                getattr(candidate, "name", ""),
                getattr(candidate, "number", ""),
            )
        )
    )
    return list(dict.fromkeys(key for key in keys if key.strip("|")))


def parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def clamp(value: float, minimum: float, maximum: float) -> int:
    return int(round(max(minimum, min(maximum, value))))


def scale_component(raw_score: float, default_maximum: float, configured_maximum: int) -> int:
    if configured_maximum <= 0 or default_maximum <= 0:
        return 0
    return clamp(
        raw_score / default_maximum * configured_maximum,
        0,
        configured_maximum,
    )


def candidate_age_years(candidate: Any) -> float | None:
    release = parse_date(getattr(candidate, "release_date", None))
    if release is None:
        return None
    now = datetime.now(timezone.utc)
    return max(0.0, (now - release).days / 365.25)


def contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(normalize_text(term) in text for term in terms)


def is_iconic(candidate: Any, settings: InvestmentSettings) -> bool:
    name = normalize_text(getattr(candidate, "name", ""))
    return any(
        normalize_text(iconic) in name
        for iconic in settings.iconic_pokemon
        if normalize_text(iconic)
    )


def lookup_override(
    candidate: Any,
    context: InvestmentContext,
) -> TargetOverride | None:
    for key in override_keys(candidate):
        override = context.overrides.get(key)
        if override and override.enabled:
            return override
    return None


def score_demand(candidate: Any, settings: InvestmentSettings) -> int:
    name = normalize_text(getattr(candidate, "name", ""))
    rarity = normalize_text(getattr(candidate, "rarity", ""))
    set_name = normalize_text(getattr(candidate, "set_name", ""))
    variant = normalize_text(getattr(candidate, "variant", ""))
    supertype = normalize_text(getattr(candidate, "supertype", ""))
    combined = " ".join((name, rarity, set_name, variant))

    score = 9.0
    if is_iconic(candidate, settings):
        score += 7
    if contains_any(combined, (
        "illustration rare", "special illustration", "alternate art",
        "alt art", "secret rare", "shiny rare", "gold star",
        "trainer gallery", "character rare", "full art",
    )):
        score += 4
    if "promo" in set_name or "promo" in rarity:
        score += 2
    if "pokemon" not in supertype and supertype:
        score -= 4
    if rarity in {"common", "uncommon"}:
        score -= 3
    return scale_component(score, 25, settings.demand_weight)


def score_scarcity(candidate: Any, settings: InvestmentSettings) -> int:
    rarity = normalize_text(getattr(candidate, "rarity", ""))
    set_name = normalize_text(getattr(candidate, "set_name", ""))
    variant = normalize_text(getattr(candidate, "variant", ""))
    combined = " ".join((rarity, set_name, variant))
    age = candidate_age_years(candidate)

    score = 7.0
    if age is not None:
        if age >= 20:
            score += 8
        elif age >= 15:
            score += 6
        elif age >= 10:
            score += 4
        elif age >= 5:
            score += 2
        elif age < 2:
            score -= 2
    if "promo" in combined:
        score += 3
    if contains_any(combined, (
        "1st edition", "first edition", "secret", "special illustration",
        "illustration rare", "gold star", "shining", "crystal",
    )):
        score += 3
    if rarity in {"common", "uncommon"}:
        score -= 3
    return scale_component(score, 20, settings.scarcity_weight)


def score_significance(candidate: Any, settings: InvestmentSettings) -> int:
    rarity = normalize_text(getattr(candidate, "rarity", ""))
    set_name = normalize_text(getattr(candidate, "set_name", ""))
    variant = normalize_text(getattr(candidate, "variant", ""))
    number = normalize_text(getattr(candidate, "number", ""))
    combined = " ".join((rarity, set_name, variant, number))
    age = candidate_age_years(candidate)

    score = 4.0
    if "promo" in combined:
        score += 3
    if contains_any(combined, (
        "special illustration", "illustration rare", "alternate art",
        "alt art", "secret", "gold star", "shining", "crystal",
        "full art", "trainer gallery", "character rare",
    )):
        score += 4
    if contains_any(combined, ("1st edition", "first edition")):
        score += 3
    if is_iconic(candidate, settings):
        score += 2
    if age is not None and age >= 15:
        score += 2
    return scale_component(score, 15, settings.significance_weight)


def score_reprint_resistance(candidate: Any, settings: InvestmentSettings) -> int:
    rarity = normalize_text(getattr(candidate, "rarity", ""))
    set_name = normalize_text(getattr(candidate, "set_name", ""))
    variant = normalize_text(getattr(candidate, "variant", ""))
    combined = " ".join((rarity, set_name, variant))
    age = candidate_age_years(candidate)

    score = 6.0
    if age is not None:
        if age >= 15:
            score += 6
        elif age >= 10:
            score += 4
        elif age >= 5:
            score += 2
        elif age < 2:
            score -= 3
    if "promo" in combined:
        score += 2
    if contains_any(combined, (
        "1st edition", "first edition", "gold star", "crystal",
        "shining", "special illustration", "alternate art", "alt art",
    )):
        score += 2
    if rarity in {"common", "uncommon"} and (age is None or age < 5):
        score -= 2
    return scale_component(score, 15, settings.reprint_weight)


def score_condition(flag: Any, details: Any, settings: InvestmentSettings) -> int:
    value = normalize_text(flag)
    text = normalize_text(details)
    if contains_any(text, ("damaged", "crease", "creased", "dent", "poor")):
        raw = 0
    elif contains_any(text, ("near mint", "mint", "pack fresh")):
        raw = 9
    elif contains_any(text, ("lightly played", "excellent")):
        raw = 6
    elif contains_any(text, ("moderately played", "played")):
        raw = 3
    elif value == "green":
        raw = 9
    elif value == "amber":
        raw = 6
    elif value == "red":
        raw = 2
    else:
        raw = 5
    return scale_component(raw, 10, settings.condition_weight)


def score_resilience(
    candidate: Any,
    context: InvestmentContext,
) -> tuple[int, str]:
    settings = context.settings
    stats = context.history.get(card_key(candidate))

    if stats and stats.count >= 3 and stats.span_days >= 30:
        ordered = sorted(stats.values, key=lambda item: item[0])
        prices = [value for _, value in ordered if value > 0]
        if len(prices) >= 3:
            first = prices[0]
            last = prices[-1]
            peak = max(prices)
            change = (last - first) / first if first else 0.0
            drawdown = (last - peak) / peak if peak else 0.0
            returns = [
                (prices[index] - prices[index - 1]) / prices[index - 1]
                for index in range(1, len(prices))
                if prices[index - 1]
            ]
            volatility = statistics.pstdev(returns) if len(returns) >= 2 else 0.0

            score = 5.0
            if -0.05 <= change <= 0.35:
                score += 2
            elif 0.35 < change <= 0.75:
                score += 1
            elif change < -0.15:
                score -= 2
            elif change > 0.75:
                score -= 1

            if drawdown >= -0.10:
                score += 2
            elif drawdown < -0.35:
                score -= 2
            elif drawdown < -0.20:
                score -= 1

            if volatility <= 0.08:
                score += 1
            elif volatility >= 0.30:
                score -= 2
            elif volatility >= 0.18:
                score -= 1

            label = "STABLE COLLECTIBLE"
            if change > 0.75:
                label = "HYPE / BREAKOUT RISK"
            elif change < -0.15:
                label = "DECLINING"
            elif change > 0.20:
                label = "STEADY RISE"
            return scale_component(score, 10, settings.resilience_weight), label

    price_change = float(getattr(candidate, "price_change", 0.0) or 0.0)
    score = 5.0
    label = "INSUFFICIENT HISTORY"
    if price_change > 0.50:
        score = 3.0
        label = "RECENT SPIKE — VERIFY"
    elif 0.05 < price_change <= 0.50:
        score = 6.0
        label = "RECENTLY RISING"
    elif price_change < -0.25:
        score = 2.0
        label = "RECENTLY FALLING"
    elif price_change < -0.05:
        score = 4.0
        label = "SOFTENING"
    return scale_component(score, 10, settings.resilience_weight), label


def score_acquisition(ratio: float | None, settings: InvestmentSettings) -> int:
    if ratio is None or not math.isfinite(ratio):
        raw = 2
    elif ratio <= 0.50:
        raw = 5
    elif ratio <= 0.65:
        raw = 4
    elif ratio <= 0.75:
        raw = 3
    elif ratio <= 0.85:
        raw = 2
    elif ratio <= 1.00:
        raw = 1
    else:
        raw = 0
    return scale_component(raw, 5, settings.acquisition_weight)


def tier_for(score: int, settings: InvestmentSettings) -> str:
    if score >= settings.core_asset_threshold:
        return "CORE ASSET"
    if score >= settings.strong_buy_threshold:
        return "STRONG LONG-TERM BUY"
    if score >= settings.selective_buy_threshold:
        return "SELECTIVE BUY"
    if score >= settings.watch_threshold:
        return "WATCH"
    if score >= 45:
        return "SPECULATIVE"
    return "AVOID FOR LONG-TERM HOLD"


def portfolio_fit_for(
    candidate: Any,
    context: InvestmentContext,
    override: TargetOverride | None,
) -> str:
    key = card_key(candidate)
    pkey = pokemon_key(getattr(candidate, "name", ""))
    card_holding = context.portfolio_by_card.get(key)
    target_quantity = (
        override.target_quantity
        if override and override.target_quantity is not None
        else context.settings.max_same_card_quantity
    )
    if card_holding and card_holding.quantity >= max(1, target_quantity):
        return "HOLDING TARGET REACHED"

    pokemon_holding = context.portfolio_by_pokemon.get(pkey)
    if (
        pokemon_holding
        and context.total_portfolio_value > 0
        and pokemon_holding.current_value / context.total_portfolio_value * 100
        >= context.settings.max_same_pokemon_percent
    ):
        return "POKÉMON CONCENTRATION RISK"
    if card_holding and card_holding.quantity > 0:
        return "ADDS TO EXISTING POSITION"
    return "GOOD FIT / NEW POSITION"


def action_for(
    score: int,
    ratio: float | None,
    tier: str,
    portfolio_fit: str,
    desired_max_ratio: float | None,
) -> str:
    if "TARGET REACHED" in portfolio_fit or "CONCENTRATION" in portfolio_fit:
        return "HOLD — DO NOT ADD"
    max_ratio = desired_max_ratio
    if max_ratio is None:
        max_ratio = {
            "CORE ASSET": 0.85,
            "STRONG LONG-TERM BUY": 0.80,
            "SELECTIVE BUY": 0.75,
            "WATCH": 0.65,
            "SPECULATIVE": 0.55,
        }.get(tier, 0.45)
    if ratio is None:
        return "RESEARCH / SET ENTRY PRICE"
    if score >= 90 and ratio <= max_ratio:
        return "CORE ASSET — ACCUMULATE"
    if score >= 80 and ratio <= max_ratio:
        return "STRONG LONG-TERM BUY"
    if score >= 70 and ratio <= max_ratio:
        return "SELECTIVE BUY"
    if score >= 60:
        return "WATCH — WAIT FOR BETTER ENTRY"
    if score >= 45:
        return "SPECULATIVE — SMALL ALLOCATION ONLY"
    return "AVOID FOR LONG-TERM HOLD"


def confidence_for(
    candidate: Any,
    context: InvestmentContext,
    condition_flag: Any,
    override: TargetOverride | None,
) -> str:
    points = 0
    if parse_date(getattr(candidate, "release_date", None)) is not None:
        points += 1
    stats = context.history.get(card_key(candidate))
    if stats and stats.count >= 3 and stats.span_days >= 30:
        points += 1
    if normalize_text(condition_flag) not in {"", "unknown", "n a"}:
        points += 1
    if override is not None:
        points += 1
    if points >= 3:
        return "HIGH"
    if points >= 2:
        return "MEDIUM"
    return "LOW"


def build_thesis(
    candidate: Any,
    score: int,
    tier: str,
    demand: int,
    scarcity: int,
    significance: int,
    ratio: float | None,
    resilience_label: str,
    hold_years: int,
) -> str:
    parts = [
        f"{getattr(candidate, 'name', '')} {getattr(candidate, 'number', '')}".strip(),
        f"rated {tier} ({score}/100)",
        f"demand {demand}/25",
        f"scarcity proxy {scarcity}/20",
        f"significance {significance}/15",
        f"price profile: {resilience_label.lower()}",
    ]
    if ratio is not None:
        parts.append(f"entry at {ratio:.0%} of current reference market")
    parts.append(f"intended hold {hold_years}+ years")
    return "; ".join(part for part in parts if part) + "."


def build_risks(
    candidate: Any,
    reprint: int,
    confidence: str,
    resilience_label: str,
    condition_score: int,
    portfolio_fit: str,
) -> str:
    risks: list[str] = []
    if reprint <= 6:
        risks.append("higher reprint/substitution risk")
    if confidence == "LOW":
        risks.append("limited historical or condition evidence")
    if "HYPE" in resilience_label or "SPIKE" in resilience_label:
        risks.append("recent price spike may not be durable")
    if "DECLINING" in resilience_label or "FALLING" in resilience_label:
        risks.append("reference market is weakening")
    if condition_score <= 4:
        risks.append("condition may limit long-term collector value")
    if "CONCENTRATION" in portfolio_fit or "TARGET REACHED" in portfolio_fit:
        risks.append("portfolio concentration or duplicate exposure")
    if candidate_age_years(candidate) is None:
        risks.append("release-date evidence unavailable")
    return "; ".join(risks) if risks else "Normal collectible-market, liquidity and valuation risk."


def assess_candidate(
    candidate: Any,
    context: InvestmentContext,
    *,
    ratio: float | None = None,
    condition_flag: Any = "UNKNOWN",
    condition_details: Any = "",
) -> InvestmentAssessment:
    settings = context.settings
    override = lookup_override(candidate, context)

    demand = score_demand(candidate, settings)
    scarcity = score_scarcity(candidate, settings)
    significance = score_significance(candidate, settings)
    reprint = score_reprint_resistance(candidate, settings)
    condition = score_condition(condition_flag, condition_details, settings)
    resilience, resilience_label = score_resilience(candidate, context)
    acquisition = score_acquisition(ratio, settings)

    if override:
        if override.demand_score is not None:
            demand = clamp(override.demand_score, 0, settings.demand_weight)
        if override.scarcity_score is not None:
            scarcity = clamp(override.scarcity_score, 0, settings.scarcity_weight)
        if override.significance_score is not None:
            significance = clamp(
                override.significance_score,
                0,
                settings.significance_weight,
            )
        if override.reprint_score is not None:
            reprint = clamp(override.reprint_score, 0, settings.reprint_weight)

    total = demand + scarcity + significance + reprint + condition + resilience + acquisition
    if override and override.total_score is not None:
        total = clamp(override.total_score, 0, 100)
    else:
        total = clamp(total, 0, 100)

    hold_years = (
        override.minimum_hold_years
        if override and override.minimum_hold_years is not None
        else settings.default_hold_years
    )
    portfolio_fit = portfolio_fit_for(candidate, context, override)
    confidence = confidence_for(candidate, context, condition_flag, override)
    tier = tier_for(total, settings)
    desired_max_ratio = override.desired_max_ratio if override else None
    action = action_for(total, ratio, tier, portfolio_fit, desired_max_ratio)

    thesis = (
        override.thesis.strip()
        if override and override.thesis.strip()
        else build_thesis(
            candidate,
            total,
            tier,
            demand,
            scarcity,
            significance,
            ratio,
            resilience_label,
            hold_years,
        )
    )
    risks = (
        override.risks.strip()
        if override and override.risks.strip()
        else build_risks(
            candidate,
            reprint,
            confidence,
            resilience_label,
            condition,
            portfolio_fit,
        )
    )

    return InvestmentAssessment(
        long_term_score=total,
        investment_tier=tier,
        long_term_action=action,
        demand_score=demand,
        scarcity_score=scarcity,
        significance_score=significance,
        reprint_score=reprint,
        condition_score=condition,
        resilience_score=resilience,
        acquisition_score=acquisition,
        data_confidence=confidence,
        portfolio_fit=portfolio_fit,
        minimum_hold_years=max(1, int(hold_years)),
        thesis=thesis,
        risks=risks,
        desired_max_ratio=desired_max_ratio,
    )


def apply_assessment(target: Any, assessment: InvestmentAssessment) -> Any:
    mapping = {
        "long_term_score": assessment.long_term_score,
        "investment_tier": assessment.investment_tier,
        "long_term_action": assessment.long_term_action,
        "demand_score": assessment.demand_score,
        "scarcity_score": assessment.scarcity_score,
        "significance_score": assessment.significance_score,
        "reprint_resistance_score": assessment.reprint_score,
        "condition_investment_score": assessment.condition_score,
        "price_resilience_score": assessment.resilience_score,
        "acquisition_discount_score": assessment.acquisition_score,
        "investment_data_confidence": assessment.data_confidence,
        "portfolio_fit": assessment.portfolio_fit,
        "minimum_hold_years": assessment.minimum_hold_years,
        "investment_thesis": assessment.thesis,
        "investment_risks": assessment.risks,
        "desired_max_ratio": assessment.desired_max_ratio,
    }
    for name, value in mapping.items():
        setattr(target, name, value)
    return target


def assessment_values(value: Any) -> list[Any]:
    return [
        int(getattr(value, "long_term_score", 0) or 0),
        str(getattr(value, "investment_tier", "") or ""),
        str(getattr(value, "long_term_action", "") or ""),
        int(getattr(value, "demand_score", 0) or 0),
        int(getattr(value, "scarcity_score", 0) or 0),
        int(getattr(value, "significance_score", 0) or 0),
        int(getattr(value, "reprint_resistance_score", 0) or 0),
        int(getattr(value, "condition_investment_score", 0) or 0),
        int(getattr(value, "price_resilience_score", 0) or 0),
        int(getattr(value, "acquisition_discount_score", 0) or 0),
        str(getattr(value, "investment_data_confidence", "") or ""),
        str(getattr(value, "portfolio_fit", "") or ""),
        int(getattr(value, "minimum_hold_years", 0) or 0),
        str(getattr(value, "investment_thesis", "") or ""),
        str(getattr(value, "investment_risks", "") or ""),
    ]


LONG_TERM_HEADERS = [
    "Long-Term Score",
    "Investment Tier",
    "Long-Term Action",
    "Demand Durability /25",
    "Scarcity Proxy /20",
    "Card Significance /15",
    "Reprint Resistance /15",
    "Condition Investment /10",
    "Price Resilience /10",
    "Acquisition Discount /5",
    "Data Confidence",
    "Portfolio Fit",
    "Minimum Hold (Years)",
    "Investment Thesis",
    "Investment Risks",
]
