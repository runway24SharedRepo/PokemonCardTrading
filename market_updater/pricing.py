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
    """Build variant prices with a conservative, auditable hierarchy.

    TCGplayer's variant-specific market price is primary. Cardmarket trend is
    used only when TCGplayer has no price for that exact variant. This prevents
    a broad Cardmarket trend from silently becoming the scanner's Normal value.
    """

    card_id = str(card.get("id", "")).strip()
    card_name = str(card.get("name", "")).strip()
    set_info = card.get("set") or {}
    set_id = str(set_info.get("id", "")).strip()
    set_name = str(set_info.get("name", "")).strip()
    number = str(card.get("number", "")).strip()

    selected: dict[str, PriceVariant] = {}

    tcgplayer = card.get("tcgplayer") or {}
    tcg_prices = tcgplayer.get("prices") or {}
    tcg_url = str(tcgplayer.get("url", "")).strip()
    tcg_date = str(tcgplayer.get("updatedAt", "")).strip()

    # 1. Variant-specific TCGplayer market is the primary source.
    for api_variant, values in tcg_prices.items():
        display_variant = TCG_VARIANT_NAMES.get(
            api_variant,
            api_variant,
        )
        value, field = first_number(
            values or {},
            config["tcgplayer_price_priority"],
        )
        if value is None:
            continue

        selected[display_variant] = PriceVariant(
            card_id=card_id,
            card_name=card_name,
            set_id=set_id,
            set_name=set_name,
            card_number=number,
            variant=display_variant,
            price_gbp=round(
                value * fx.usd_to_gbp,
                2,
            ),
            source=(
                "Pokémon TCG API / TCGplayer "
                "(primary market)"
            ),
            source_date=tcg_date,
            source_url=tcg_url,
            original_price=value,
            original_currency="USD",
            source_field=field,
        )

    cardmarket = card.get("cardmarket") or {}
    cardmarket_prices = (
        cardmarket.get("prices") or {}
    )
    cardmarket_url = str(
        cardmarket.get("url", "")
    ).strip()
    cardmarket_date = str(
        cardmarket.get("updatedAt", "")
    ).strip()

    edition_sensitive = any(
        key in tcg_prices
        for key in (
            "1stEditionNormal",
            "1stEditionHolofoil",
        )
    )

    # 2. Cardmarket is only a fallback for an exact variant with no TCG price.
    if "Normal" not in selected and not edition_sensitive:
        value, field = first_number(
            cardmarket_prices,
            config[
                "cardmarket_normal_price_priority"
            ],
        )
        if value is not None:
            selected["Normal"] = PriceVariant(
                card_id=card_id,
                card_name=card_name,
                set_id=set_id,
                set_name=set_name,
                card_number=number,
                variant="Normal",
                price_gbp=round(
                    value * fx.eur_to_gbp,
                    2,
                ),
                source=(
                    "Pokémon TCG API / Cardmarket "
                    "(fallback trend)"
                ),
                source_date=cardmarket_date,
                source_url=cardmarket_url,
                original_price=value,
                original_currency="EUR",
                source_field=field,
            )

    if "Reverse Holofoil" not in selected:
        value, field = first_number(
            cardmarket_prices,
            config[
                "cardmarket_reverse_price_priority"
            ],
        )
        if value is not None:
            selected[
                "Reverse Holofoil"
            ] = PriceVariant(
                card_id=card_id,
                card_name=card_name,
                set_id=set_id,
                set_name=set_name,
                card_number=number,
                variant="Reverse Holofoil",
                price_gbp=round(
                    value * fx.eur_to_gbp,
                    2,
                ),
                source=(
                    "Pokémon TCG API / Cardmarket "
                    "(fallback trend)"
                ),
                source_date=cardmarket_date,
                source_url=cardmarket_url,
                original_price=value,
                original_currency="EUR",
                source_field=field,
            )

    return sorted(
        selected.values(),
        key=lambda item: (
            item.variant.casefold(),
            item.card_id.casefold(),
        ),
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
