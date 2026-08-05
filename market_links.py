from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus


@dataclass(frozen=True)
class CardMarketLinks:
    uk_market: str
    tcgplayer: str
    cardmarket: str
    pricecharting: str


def _plain_ascii(value: Any) -> str:
    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    return "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )


def _clean_card_name(value: Any) -> str:
    """Return a marketplace-friendly card name without punctuation.

    Examples:
      Kyogre-EX       -> Kyogre EX
      N's Zekrom      -> Ns Zekrom
      Farfetch'd      -> Farfetchd
      Type: Null      -> Type Null
      Nidoran♀        -> Nidoran F
      Nidoran♂        -> Nidoran M
    """

    text = _plain_ascii(value)
    text = text.replace("♀", " F ")
    text = text.replace("♂", " M ")
    text = text.replace("&", " and ")

    # Apostrophes are removed rather than changed to spaces so:
    # N's -> Ns and Farfetch'd -> Farfetchd.
    text = re.sub(r"['’`´]+", "", text)

    # Hyphens, colons, slashes and all other punctuation become spaces.
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_collector_identifier(
    number: Any,
    card_id: Any = "",
) -> str:
    """Return the printed collector number or a compact ID fallback.

    Slash numbers use only the collector-number side:
      58/102     -> 58
      TG06/TG30  -> TG06

    When Card Number is empty, the final useful token from Card ID is used:
      base1-58   -> 58
      xy-p-xy41  -> XY41
    """

    raw_number = _plain_ascii(number).strip()
    if raw_number:
        first = raw_number.split("/", 1)[0].strip()
        cleaned = re.sub(r"[^A-Za-z0-9]+", "", first)
        if cleaned:
            return cleaned.upper() if any(
                character.isalpha()
                for character in cleaned
            ) else cleaned

    raw_id = _plain_ascii(card_id).strip()
    if not raw_id:
        return ""

    tokens = [
        token
        for token in re.split(r"[^A-Za-z0-9]+", raw_id)
        if token
    ]
    if not tokens:
        return ""

    candidate = tokens[-1]
    return candidate.upper() if any(
        character.isalpha()
        for character in candidate
    ) else candidate


def card_market_query(
    name: Any,
    set_name: Any = "",
    number: Any = "",
    variant: Any = "",
    card_id: Any = "",
) -> str:
    """Build the canonical tracker query: clean card name + number/ID.

    set_name and variant remain accepted for backward compatibility but are
    intentionally excluded from the query because they often prevent tracker
    search engines from finding the card.
    """

    del set_name, variant

    clean_name = _clean_card_name(name)
    identifier = _clean_collector_identifier(
        number,
        card_id,
    )
    return " ".join(
        value
        for value in (clean_name, identifier)
        if value
    ).strip()


def market_links_for_fields(
    name: Any,
    set_name: Any,
    number: Any,
    variant: Any = "",
    card_id: Any = "",
) -> CardMarketLinks:
    query = card_market_query(
        name=name,
        set_name=set_name,
        number=number,
        variant=variant,
        card_id=card_id,
    )
    encoded = quote_plus(query)

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
            f"q={encoded}&type=prices"
        ),
    )


def market_links_for_candidate(candidate: Any) -> CardMarketLinks:
    return market_links_for_fields(
        getattr(candidate, "name", ""),
        getattr(candidate, "set_name", ""),
        getattr(candidate, "number", ""),
        getattr(candidate, "variant", ""),
        getattr(candidate, "card_id", ""),
    )


def market_link_values(candidate: Any) -> tuple[str, str, str, str]:
    links = market_links_for_candidate(candidate)
    return (
        links.uk_market,
        links.tcgplayer,
        links.cardmarket,
        links.pricecharting,
    )
