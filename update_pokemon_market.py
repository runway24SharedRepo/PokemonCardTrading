from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from market_updater.api import (
    PokemonTcgClient,
    fetch_fx_rates,
    save_gzip_snapshot,
)
from market_updater.csv_export import export_latest_files
from market_updater.database import MarketDatabase
from market_updater.excel_writer import write_workbook
from market_updater.pricing import PriceVariant, build_price_variants


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the full Pokémon card database and market prices."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test API and FX access without changing files.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Diagnostic page limit. Omit for the complete database.",
    )
    parser.add_argument(
        "--no-excel",
        action="store_true",
        help="Update local database/CSV files without touching Excel.",
    )
    return parser.parse_args()


def load_config(root: Path) -> dict[str, Any]:
    path = root / "market-updater-config.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing configuration file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def progress(**values: Any) -> None:
    total = values["total_count"]
    accumulated = values["accumulated"]
    percent = (accumulated / total * 100) if total else 0
    print(
        f"Page {values['page']}: "
        f"{accumulated}/{total} cards ({percent:.1f}%)",
        flush=True,
    )


def build_changes(
    prices: list[PriceVariant],
    previous: dict[tuple[str, str], float],
    tolerance: float,
    observed_at: str,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    for price in prices:
        key = (price.card_id, price.variant)
        previous_price = previous.get(key)
        if previous_price is None:
            continue

        difference = round(price.price_gbp - previous_price, 2)
        if abs(difference) < tolerance:
            continue

        change_percent = (
            difference / previous_price if previous_price else 0.0
        )
        changes.append(
            {
                "observed_at": observed_at,
                "card_id": price.card_id,
                "card_name": price.card_name,
                "set_name": price.set_name,
                "card_number": price.card_number,
                "variant": price.variant,
                "previous_price_gbp": previous_price,
                "current_price_gbp": price.price_gbp,
                "change_gbp": difference,
                "change_percent": change_percent,
                "source": price.source,
                "source_date": price.source_date,
                "source_url": price.source_url,
            }
        )

    return changes


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent

    load_dotenv(root / ".env", override=True, encoding="utf-8-sig")
    config = load_config(root)

    api_key = os.getenv("POKEMON_TCG_API_KEY", "").strip()
    delay_seconds = (
        float(config["request_delay_with_key_seconds"])
        if api_key
        else float(config["request_delay_without_key_seconds"])
    )

    client = PokemonTcgClient(
        api_url=config["pokemon_tcg_api_url"],
        api_key=api_key,
        page_size=int(config["page_size"]),
        delay_seconds=delay_seconds,
        timeout_seconds=int(config["request_timeout_seconds"]),
        retry_attempts=int(config["retry_attempts"]),
    )

    data_folder = root / "data"
    backup_folder = root / "backups"
    database = MarketDatabase(data_folder / "pokemon-card-market.sqlite")
    run_id = database.start_run()

    try:
        previous_fx = database.previous_fx_rates()
        fx = fetch_fx_rates(
            session=requests.Session(),
            api_url=config["fx_api_url"],
            timeout_seconds=int(config["request_timeout_seconds"]),
            eur_override=os.getenv("MARKET_EUR_TO_GBP_OVERRIDE", ""),
            usd_override=os.getenv("MARKET_USD_TO_GBP_OVERRIDE", ""),
            previous_rates=previous_fx,
        )

        if args.test:
            test_result = client.test_connection()
            print("Pokémon TCG API connection: OK")
            print(f"API key used: {'YES' if test_result['api_key_used'] else 'NO'}")
            print(f"API reported total cards: {test_result['total_count']}")
            print(f"EUR -> GBP: {fx.eur_to_gbp:.6f}")
            print(f"USD -> GBP: {fx.usd_to_gbp:.6f}")
            database.fail_run(run_id, "Connection test only; no update performed.")
            return 0

        print("Downloading the full English Pokémon card catalogue...")
        cards, download_metadata = client.fetch_all_cards(
            progress=progress,
            maximum_pages=args.max_pages,
        )

        variants_by_card: dict[str, list[PriceVariant]] = defaultdict(list)
        prices: list[PriceVariant] = []

        for card in cards:
            card_variants = build_price_variants(card, fx, config)
            card_id = str(card.get("id", ""))
            variants_by_card[card_id].extend(card_variants)
            prices.extend(card_variants)

        prices.sort(
            key=lambda value: (
                value.set_name.casefold(),
                value.card_name.casefold(),
                value.card_number.casefold(),
                value.variant.casefold(),
            )
        )

        observed_at = datetime.now().astimezone().isoformat(timespec="seconds")
        previous_prices = database.current_price_map()
        changes = build_changes(
            prices=prices,
            previous=previous_prices,
            tolerance=float(config["price_change_tolerance_gbp"]),
            observed_at=observed_at,
        )

        sync_metadata = {
            **download_metadata,
            "synced_at": observed_at,
            "api_key_used": bool(api_key),
        }

        if config.get("save_compressed_api_snapshot", True):
            save_gzip_snapshot(
                cards=cards,
                path=data_folder / "pokemon-tcg-api-latest.json.gz",
                metadata=sync_metadata,
            )

        export_latest_files(
            data_folder=data_folder,
            cards=cards,
            variants_by_card=variants_by_card,
            prices=prices,
            changes=changes,
            synced_at=observed_at,
        )

        excel_result = {}
        if not args.no_excel:
            workbook_path = Path(
                os.getenv(
                    "WORKBOOK_PATH",
                    config["workbook_filename"],
                )
            )
            if not workbook_path.is_absolute():
                workbook_path = root / workbook_path

            excel_result = write_workbook(
                workbook_path=workbook_path,
                backup_folder=backup_folder,
                cards=cards,
                prices=prices,
                variants_by_card=variants_by_card,
                changes=changes,
                fx=fx,
                sync_metadata=sync_metadata,
                config=config,
            )

        database.commit_sync(
            run_id=run_id,
            cards=cards,
            prices=prices,
            fx=fx,
            changed_prices=changes,
        )

        print()
        print("DAILY MARKET UPDATE SUCCESSFUL")
        print(f"Cards downloaded: {len(cards)}")
        print(f"Priced variants: {len(prices)}")
        print(f"Price changes: {len(changes)}")
        print(f"EUR -> GBP: {fx.eur_to_gbp:.6f}")
        print(f"USD -> GBP: {fx.usd_to_gbp:.6f}")
        if excel_result:
            print(
                "Excel Market Data Import rows: "
                f"{excel_result['market_rows_written']}"
            )
            print(
                "Excel Full Card Database rows: "
                f"{excel_result['database_rows_written']}"
            )
            print(f"Workbook backup: {excel_result['backup_path']}")
        return 0

    except Exception as exc:
        database.fail_run(run_id, repr(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
