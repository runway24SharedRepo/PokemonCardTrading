from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class FxRates:
    eur_to_gbp: float
    usd_to_gbp: float
    source: str
    rate_date: str


@dataclass(frozen=True)
class PriceVariant:
    card_id: str
    card_name: str
    set_id: str
    set_name: str
    card_number: str
    variant: str
    price_gbp: float
    source: str
    source_date: str
    source_url: str
    original_price: float
    original_currency: str
    source_field: str


TCG_VARIANT_NAMES = {
    "normal": "Normal",
    "holofoil": "Holofoil",
    "reverseHolofoil": "Reverse Holofoil",
    "1stEditionHolofoil": "1st Edition Holofoil",
    "1stEditionNormal": "1st Edition Normal",
}


def first_number(
    values: dict[str, Any],
    priority: Iterable[str],
) -> tuple[float | None, str]:
    for field in priority:
        value = values.get(field)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number, field
    return None, ""


def build_price_variants(
    card: dict[str, Any],
    fx: FxRates,
    config: dict[str, Any],
) -> list[PriceVariant]:
    card_id = str(card.get("id", "")).strip()
    card_name = str(card.get("name", "")).strip()
    set_info = card.get("set") or {}
    set_id = str(set_info.get("id", "")).strip()
    set_name = str(set_info.get("name", "")).strip()
    number = str(card.get("number", "")).strip()

    selected: dict[str, PriceVariant] = {}

    # Cardmarket is preferred for Normal and Reverse Holo because the user's
    # market is the UK and Cardmarket is Europe-oriented.
    cardmarket = card.get("cardmarket") or {}
    cardmarket_prices = cardmarket.get("prices") or {}
    cardmarket_url = str(cardmarket.get("url", "")).strip()
    cardmarket_date = str(cardmarket.get("updatedAt", "")).strip()

    normal_value, normal_field = first_number(
        cardmarket_prices,
        config["cardmarket_normal_price_priority"],
    )
    if normal_value is not None:
        selected["Normal"] = PriceVariant(
            card_id=card_id,
            card_name=card_name,
            set_id=set_id,
            set_name=set_name,
            card_number=number,
            variant="Normal",
            price_gbp=round(normal_value * fx.eur_to_gbp, 2),
            source="Pokémon TCG API / Cardmarket",
            source_date=cardmarket_date,
            source_url=cardmarket_url,
            original_price=normal_value,
            original_currency="EUR",
            source_field=normal_field,
        )

    reverse_value, reverse_field = first_number(
        cardmarket_prices,
        config["cardmarket_reverse_price_priority"],
    )
    if reverse_value is not None:
        selected["Reverse Holofoil"] = PriceVariant(
            card_id=card_id,
            card_name=card_name,
            set_id=set_id,
            set_name=set_name,
            card_number=number,
            variant="Reverse Holofoil",
            price_gbp=round(reverse_value * fx.eur_to_gbp, 2),
            source="Pokémon TCG API / Cardmarket",
            source_date=cardmarket_date,
            source_url=cardmarket_url,
            original_price=reverse_value,
            original_currency="EUR",
            source_field=reverse_field,
        )

    # TCGplayer fills variant gaps and supplies foil/first-edition variants.
    tcgplayer = card.get("tcgplayer") or {}
    tcg_prices = tcgplayer.get("prices") or {}
    tcg_url = str(tcgplayer.get("url", "")).strip()
    tcg_date = str(tcgplayer.get("updatedAt", "")).strip()

    for api_variant, values in tcg_prices.items():
        display_variant = TCG_VARIANT_NAMES.get(api_variant, api_variant)
        value, field = first_number(
            values or {},
            config["tcgplayer_price_priority"],
        )
        if value is None:
            continue

        candidate = PriceVariant(
            card_id=card_id,
            card_name=card_name,
            set_id=set_id,
            set_name=set_name,
            card_number=number,
            variant=display_variant,
            price_gbp=round(value * fx.usd_to_gbp, 2),
            source="Pokémon TCG API / TCGplayer",
            source_date=tcg_date,
            source_url=tcg_url,
            original_price=value,
            original_currency="USD",
            source_field=field,
        )

        # Keep Cardmarket for Normal and Reverse Holo; use TCGplayer otherwise.
        if display_variant not in selected:
            selected[display_variant] = candidate

    return sorted(
        selected.values(),
        key=lambda item: (item.variant.casefold(), item.card_id.casefold()),
    )


def best_price_summary(
    variants: list[PriceVariant],
) -> tuple[float | None, str, str]:
    if not variants:
        return None, "", ""

    preference = {
        "Normal": 0,
        "Holofoil": 1,
        "Reverse Holofoil": 2,
        "1st Edition Normal": 3,
        "1st Edition Holofoil": 4,
    }
    best = sorted(
        variants,
        key=lambda value: (
            preference.get(value.variant, 99),
            value.price_gbp,
        ),
    )[0]
    return best.price_gbp, best.variant, best.source
