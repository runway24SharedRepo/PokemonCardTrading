from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FxRates:
    """Reference rates expressed as GBP received for one source-currency unit."""

    eur_to_gbp: float
    usd_to_gbp: float
    source: str
    rate_date: str

    @property
    def usd_per_gbp(self) -> float:
        return 1.0 / self.usd_to_gbp


@dataclass(frozen=True)
class PriceVariant:
    card_id: str
    card_name: str
    set_id: str
    set_name: str
    card_number: str
    variant: str
    price_gbp: float | None
    source: str
    source_date: str
    source_url: str
    original_price: float | None
    original_currency: str
    source_field: str
    finish: str = "Unspecified"
    edition: str = "Unspecified"
    selected_price_category: str = ""
    exchange_rate_to_gbp: float = 0.0
    match_status: str = ""
    available_variants: str = ""
    notes: str = ""

    @property
    def has_market_price(self) -> bool:
        # Kept for compatibility with the scanner and manual-control modules.
        return self.price_gbp is not None and self.price_gbp > 0


OFFICIAL_VARIANTS = {
    "normal": ("Normal", "Normal", "Unlimited"),
    "holofoil": ("Holofoil", "Holofoil", "Unlimited"),
    "reverseHolofoil": (
        "Reverse Holofoil",
        "Reverse Holofoil",
        "Unlimited",
    ),
    "1stEditionNormal": (
        "1st Edition Normal",
        "Normal",
        "1st Edition",
    ),
    "1stEditionHolofoil": (
        "1st Edition Holofoil",
        "Holofoil",
        "1st Edition",
    ),
    "unlimitedHolofoil": (
        "Holofoil",
        "Holofoil",
        "Unlimited",
    ),
}


def _positive(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _rarity_is_holo(card: dict[str, Any]) -> bool:
    return "holo" in str(card.get("rarity", "")).casefold()


def _category_identity(
    card: dict[str, Any],
    category: str,
) -> tuple[str, str, str] | None:
    if category in OFFICIAL_VARIANTS:
        return OFFICIAL_VARIANTS[category]
    if category == "unlimited":
        if _rarity_is_holo(card):
            return ("Holofoil", "Holofoil", "Unlimited")
        return ("Normal", "Normal", "Unlimited")
    if category == "1stEdition":
        if _rarity_is_holo(card):
            return ("1st Edition Holofoil", "Holofoil", "1st Edition")
        return ("1st Edition Normal", "Normal", "1st Edition")
    return None


def _cardmarket_description(prices: dict[str, Any]) -> str:
    fields = (
        "averageSellPrice",
        "reverseHoloSell",
        "avg1",
        "avg7",
        "avg30",
        "reverseHoloAvg1",
        "reverseHoloAvg7",
        "reverseHoloAvg30",
    )
    parts: list[str] = []
    for field in fields:
        value = _positive(prices.get(field))
        parts.append(
            f"{field}=" + (f"EUR {value:.2f}" if value is not None else "unavailable")
        )
    return "; ".join(parts)


def _mapped_identities(card: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    tcg_prices = ((card.get("tcgplayer") or {}).get("prices") or {})
    output: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for category in tcg_prices:
        identity = _category_identity(card, str(category))
        if identity is None or identity in seen:
            continue
        output.append((*identity, str(category)))
        seen.add(identity)

    if output:
        return output

    # Some API records have Cardmarket data but no TCGplayer categories. In
    # that case the printed rarity identifies the standard finish. A reverse
    # row is added only when Cardmarket explicitly returns reverse-holo sales.
    standard = (
        ("Holofoil", "Holofoil", "Unlimited", "printed-holo")
        if _rarity_is_holo(card)
        else ("Normal", "Normal", "Unlimited", "printed-normal")
    )
    output.append(standard)
    cm_prices = ((card.get("cardmarket") or {}).get("prices") or {})
    if _positive(cm_prices.get("reverseHoloAvg30")) is not None:
        output.append(
            (
                "Reverse Holofoil",
                "Reverse Holofoil",
                "Unlimited",
                "cardmarket-reverse",
            )
        )
    return output


def _standard_finish(
    card: dict[str, Any],
    identities: list[tuple[str, str, str, str]],
) -> str | None:
    unlimited_standard = {
        finish
        for _, finish, edition, _ in identities
        if edition == "Unlimited" and finish in {"Normal", "Holofoil"}
    }
    if len(unlimited_standard) == 1:
        return next(iter(unlimited_standard))
    if len(unlimited_standard) > 1:
        rarity_finish = "Holofoil" if _rarity_is_holo(card) else "Normal"
        return rarity_finish if rarity_finish in unlimited_standard else None
    return None


def build_price_variants(
    card: dict[str, Any],
    fx: FxRates,
    config: dict[str, Any] | None = None,
) -> list[PriceVariant]:
    """Build strict Cardmarket rolling 30-day average-selling-price records.

    Column H may receive only ``cardmarket.prices.avg30`` for the card's
    standard Unlimited finish or ``reverseHoloAvg30`` for Reverse Holofoil.
    The non-windowed averageSellPrice, trend, shorter rolling averages,
    TCGplayer market and high/mid/low values are audit-only and never
    substitute for the requested metric. Cardmarket does not distinguish First
    Edition in this API payload, so First Edition rows remain unavailable
    unless a verified manual override exists.
    """

    card_id = str(card.get("id", "")).strip()
    card_name = str(card.get("name", "")).strip()
    set_info = card.get("set") or {}
    set_id = str(set_info.get("id", "")).strip()
    set_name = str(set_info.get("name", "")).strip()
    card_number = str(card.get("number", "")).strip()
    cardmarket = card.get("cardmarket") or {}
    cm_prices = cardmarket.get("prices") or {}
    source_url = str(cardmarket.get("url", "")).strip()
    source_date = str(cardmarket.get("updatedAt", "")).strip()
    available = _cardmarket_description(cm_prices)
    identities = _mapped_identities(card)
    standard_finish = _standard_finish(card, identities)
    records: list[PriceVariant] = []

    for variant, finish, edition, identity_source in identities:
        source_field = ""
        original_price: float | None = None
        status = "PRICE UNAVAILABLE"
        notes = ""

        if edition == "1st Edition":
            status = "PRICE UNAVAILABLE - EDITION NOT SEPARATED"
            notes = (
                "Cardmarket avg30 does not identify First Edition "
                "separately; the standard average was not substituted."
            )
        elif finish == "Reverse Holofoil":
            source_field = "cardmarket.prices.reverseHoloAvg30"
            original_price = _positive(cm_prices.get("reverseHoloAvg30"))
            status = (
                "EXACT CARDMARKET 30-DAY AVERAGE"
                if original_price is not None
                else "PRICE UNAVAILABLE"
            )
            notes = (
                "Reverse-holo 30-day average selling price selected."
                if original_price is not None
                else "Cardmarket reverseHoloAvg30 is missing; no substitute was used."
            )
        elif finish == standard_finish:
            source_field = "cardmarket.prices.avg30"
            original_price = _positive(cm_prices.get("avg30"))
            status = (
                "EXACT CARDMARKET 30-DAY AVERAGE"
                if original_price is not None
                else "PRICE UNAVAILABLE"
            )
            notes = (
                "Standard-finish 30-day average selling price selected."
                if original_price is not None
                else "Cardmarket avg30 is missing; no substitute was used."
            )
        else:
            status = "PRICE UNAVAILABLE - FINISH NOT SEPARATED"
            notes = (
                "Cardmarket exposes one standard average for this product and "
                "the requested finish could not be isolated safely."
            )

        price_gbp = (
            round(original_price * fx.eur_to_gbp, 2)
            if original_price is not None
            else None
        )
        records.append(
            PriceVariant(
                card_id=card_id,
                card_name=card_name,
                set_id=set_id,
                set_name=set_name,
                card_number=card_number,
                variant=variant,
                finish=finish,
                edition=edition,
                selected_price_category=identity_source,
                price_gbp=price_gbp,
                source="Pokémon TCG API / Cardmarket 30-day average selling price",
                source_date=source_date,
                source_url=source_url,
                original_price=original_price,
                original_currency="EUR",
                source_field=source_field,
                exchange_rate_to_gbp=fx.eur_to_gbp,
                match_status=status,
                available_variants=available,
                notes=notes,
            )
        )

    return sorted(records, key=lambda item: item.variant.casefold())


def available_price_variants(records: list[PriceVariant]) -> list[PriceVariant]:
    output: list[PriceVariant] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record.card_id.casefold(), record.variant.casefold())
        if record.has_market_price and key not in seen:
            output.append(record)
            seen.add(key)
    return output


def best_price_summary(
    variants: list[PriceVariant],
) -> tuple[float | None, str, str]:
    priced = available_price_variants(variants)
    if not priced:
        return None, "", ""

    preference = {
        "Normal": 0,
        "Holofoil": 1,
        "Reverse Holofoil": 2,
    }
    best = sorted(
        priced,
        key=lambda value: (
            preference.get(value.variant, 99),
            float(value.price_gbp or 0),
        ),
    )[0]
    return best.price_gbp, best.variant, best.source
