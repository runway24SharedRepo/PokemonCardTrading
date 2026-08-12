from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .pricing import PriceVariant, best_price_summary


def _atomic_csv(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    temp.replace(path)


def export_latest_files(
    data_folder: Path,
    cards: list[dict[str, Any]],
    variants_by_card: dict[str, list[PriceVariant]],
    prices: list[PriceVariant],
    changes: list[dict[str, Any]],
    synced_at: str,
) -> None:
    database_headers = [
        "Card ID",
        "Card Name",
        "Set ID",
        "Set Name",
        "Series",
        "Card Number",
        "Printed Total",
        "Rarity",
        "Supertype",
        "Subtypes",
        "Types",
        "HP",
        "Artist",
        "Release Date",
        "Regulation Mark",
        "Evolves From",
        "Evolves To",
        "Best 30-Day Average Selling Price GBP",
        "Best Variant",
        "Best Source",
        "Image URL",
        "Last Synced",
    ]

    database_rows: list[list[Any]] = []
    for card in cards:
        set_info = card.get("set") or {}
        images = card.get("images") or {}
        card_variants = variants_by_card.get(str(card.get("id", "")), [])
        best_price, best_variant, best_source = best_price_summary(card_variants)
        database_rows.append(
            [
                card.get("id", ""),
                card.get("name", ""),
                set_info.get("id", ""),
                set_info.get("name", ""),
                set_info.get("series", ""),
                card.get("number", ""),
                set_info.get("printedTotal", ""),
                card.get("rarity", ""),
                card.get("supertype", ""),
                " | ".join(card.get("subtypes") or []),
                " | ".join(card.get("types") or []),
                card.get("hp", ""),
                card.get("artist", ""),
                set_info.get("releaseDate", ""),
                card.get("regulationMark", ""),
                card.get("evolvesFrom", ""),
                " | ".join(card.get("evolvesTo") or []),
                best_price if best_price is not None else "",
                best_variant,
                best_source,
                images.get("large", ""),
                synced_at,
            ]
        )

    _atomic_csv(
        data_folder / "pokemon-card-database.csv",
        database_headers,
        database_rows,
    )

    market_headers = [
        "Enabled",
        "Card Name",
        "Set Name",
        "Card Number",
        "Variant",
        "Language",
        "Condition",
        "Average Selling Price (£)",
        "Source",
        "Source Date",
        "Source URL",
        "Notes",
        "Card ID",
    ]
    market_rows = [
        [
            "YES",
            price.card_name,
            price.set_name,
            price.card_number,
            price.variant,
            "English",
            "Average selling price",
            price.price_gbp,
            price.source,
            price.source_date,
            price.source_url,
            (
                f"{price.original_currency} {price.original_price:.2f} "
                f"{price.source_field}; converted to GBP. "
                "30-day average; verify exact condition and printing before bidding."
            ),
            price.card_id,
        ]
        for price in prices
    ]
    _atomic_csv(
        data_folder / "pokemon-card-market.csv",
        market_headers,
        market_rows,
    )

    change_headers = [
        "Observed At",
        "Card ID",
        "Card Name",
        "Set Name",
        "Card Number",
        "Variant",
        "Previous Price (£)",
        "Current Price (£)",
        "Change (£)",
        "Change (%)",
        "Source",
        "Source Date",
        "Source URL",
    ]
    change_rows = [
        [
            change["observed_at"],
            change["card_id"],
            change["card_name"],
            change["set_name"],
            change["card_number"],
            change["variant"],
            change["previous_price_gbp"],
            change["current_price_gbp"],
            change["change_gbp"],
            change["change_percent"],
            change["source"],
            change["source_date"],
            change["source_url"],
        ]
        for change in changes
    ]
    _atomic_csv(
        data_folder / "pokemon-card-price-changes.csv",
        change_headers,
        change_rows,
    )
