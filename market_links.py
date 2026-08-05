from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus


@dataclass(frozen=True)
class CardMarketLinks:
    uk_market: str
    tcgplayer: str
    cardmarket: str
    pricecharting: str


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _variant_text(value: Any) -> str:
    text = _clean(value)
    if text.casefold() in {"", "normal", "standard"}:
        return ""
    return text


def card_market_query(
    name: Any,
    set_name: Any,
    number: Any,
    variant: Any = "",
) -> str:
    parts = [
        _clean(name),
        _clean(set_name),
        _clean(number),
        _variant_text(variant),
    ]
    return _clean(" ".join(part for part in parts if part))


def market_links_for_fields(
    name: Any,
    set_name: Any,
    number: Any,
    variant: Any = "",
) -> CardMarketLinks:
    query = card_market_query(name, set_name, number, variant)
    encoded = quote_plus(query)
    pricecharting_query = quote_plus(
        _clean(f"Pokemon {query}")
    )
    return CardMarketLinks(
        uk_market=(
            "https://cardmetric.co.uk/search?"
            f"q={encoded}"
        ),
        tcgplayer=(
            "https://www.tcgplayer.com/search/pokemon/product?"
            "productLineName=pokemon&view=grid&"
            f"q={encoded}"
        ),
        cardmarket=(
            "https://www.cardmarket.com/en/Pokemon/Products/Search?"
            f"searchString={encoded}"
        ),
        pricecharting=(
            "https://www.pricecharting.com/search-products?"
            f"q={pricecharting_query}&type=prices"
        ),
    )


def market_links_for_candidate(candidate: Any) -> CardMarketLinks:
    return market_links_for_fields(
        getattr(candidate, "name", ""),
        getattr(candidate, "set_name", ""),
        getattr(candidate, "number", ""),
        getattr(candidate, "variant", ""),
    )


def market_link_values(candidate: Any) -> tuple[str, str, str, str]:
    links = market_links_for_candidate(candidate)
    return (
        links.uk_market,
        links.tcgplayer,
        links.cardmarket,
        links.pricecharting,
    )
