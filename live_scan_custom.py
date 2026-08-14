from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from random_range_sniper import evaluate_item, enrich_result_condition
from random_sniper.core import (
    ListingResult,
    build_queries,
    ebay_auction_search_url,
    ebay_buy_now_search_url,
    ebay_sold_search_url,
)
from random_sniper.ebay_client import EbayBrowseClient
from random_sniper.excel_adapter import ExcelAdapter
from random_sniper.seller_discovery import CandidateTitleMatcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan live eBay UK listings only for Market Data Import column-H "
            "rows selected in pokemonInput.txt."
        )
    )
    parser.add_argument(
        "--input",
        default="pokemonInput.txt",
        help="Input file containing one H-row reference per line.",
    )
    parser.add_argument("--test-api", action="store_true")
    return parser.parse_args()


def configure_logging(root: Path) -> logging.Logger:
    logger = logging.getLogger("custom-live-scan")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(
        root / "custom-live-scan.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    logger = configure_logging(root)
    load_dotenv(root / ".env", override=True, encoding="utf-8-sig")

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = root / input_path
    if not input_path.exists():
        raise FileNotFoundError(
            f"Custom card input file not found: {input_path}"
        )

    config_path = root / "random-sniper-config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Scanner configuration not found: {config_path}"
        )
    config = json.loads(config_path.read_text(encoding="utf-8"))

    workbook_path = Path(
        os.getenv(
            "WORKBOOK_PATH",
            "Pokemon-Auction-Scanner-Dashboard.xlsx",
        )
    )
    if not workbook_path.is_absolute():
        workbook_path = root / workbook_path
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    client = None
    excel = None
    staging_path = (
        workbook_path.parent
        / f".{workbook_path.stem}.custom-live-{os.getpid()}{workbook_path.suffix}"
    )
    committed = False

    try:
        if args.test_api:
            client = EbayBrowseClient(
                config,
                root / "data" / "custom-live-scan.sqlite",
            )
            result = client.test_connection()
            print("EBAY CUSTOM LIVE SCAN API CONNECTION SUCCESSFUL")
            print(f"Marketplace: {result['marketplace']}")
            print(f"Access token received: YES ({result['token_length']} characters)")
            return 0

        shutil.copy2(workbook_path, staging_path)
        excel = ExcelAdapter(staging_path)
        settings = excel.read_settings()
        settings.selection_mode = "Custom Input — Market Data Import column H"
        settings.search_depth = "Fast"
        settings.replace_no_results = False
        settings.expand_green_sellers = False
        settings.copy_green_to_main_queue = False

        candidates = excel.read_custom_candidates(input_path)
        logger.info(
            "CUSTOM INPUT | %s exact card row(s) loaded from %s",
            len(candidates),
            input_path.name,
        )
        for candidate in candidates:
            logger.info(
                "CUSTOM CARD | %s | %s | %s | %s | reference=£%.2f | %s",
                candidate.name,
                candidate.set_name,
                candidate.number,
                candidate.variant,
                candidate.market_value,
                candidate.source.replace("Manual Market Data Import ", ""),
            )

        client = EbayBrowseClient(
            config,
            root / "data" / "custom-live-scan.sqlite",
        )
        matcher = CandidateTitleMatcher(candidates)
        exclusions = list(config["default_exclusions"])
        attempts: list[dict] = []
        all_results: list[ListingResult] = []
        api_calls = 0
        item_detail_calls = 0

        for candidate in candidates:
            query = build_queries(candidate, "Fast")[0]
            active_url = ebay_auction_search_url(query)
            buy_now_url = ebay_buy_now_search_url(query)
            sold_url = ebay_sold_search_url(query)
            logger.info(
                "SEARCHING | %s | %s | %s | %s | manual H reference £%.2f",
                candidate.name,
                candidate.set_name,
                candidate.number,
                candidate.variant,
                candidate.market_value,
            )

            items = client.search_listings(query, settings.listing_formats)
            api_calls += 1
            card_results: list[ListingResult] = []
            seen_items: set[str] = set()

            for item in items:
                item_id = str(item.get("itemId", "") or "")
                if not item_id or item_id in seen_items:
                    continue
                seen_items.add(item_id)
                detected = matcher.match(
                    str(item.get("title", "") or ""),
                    exclusions,
                )
                if detected is None or detected.identity != candidate.identity:
                    continue
                evaluated = evaluate_item(
                    candidate,
                    item,
                    query,
                    settings,
                    exclusions,
                )
                if evaluated is None:
                    continue
                evaluated.discovery_source = "CUSTOM INPUT"
                if enrich_result_condition(
                    evaluated,
                    item,
                    client,
                    logger,
                ):
                    item_detail_calls += 1
                card_results.append(evaluated)

            card_results.sort(
                key=lambda item: (
                    not item.queue_eligible,
                    item.decision != "GREEN",
                    item.decision == "RED",
                    -item.score,
                    item.minutes_remaining,
                )
            )
            all_results.extend(card_results)
            best = min(card_results, key=lambda item: item.ratio, default=None)
            attempts.append(
                {
                    "candidate": candidate,
                    "status": "RESULTS FOUND" if card_results else "NO RESULTS",
                    "queries_run": 1,
                    "listings_found": len(card_results),
                    "results": card_results,
                    "best_result": best,
                    "target_ratio": settings.target_ratio,
                    "active_search_url": active_url,
                    "buy_now_search_url": buy_now_url,
                    "sold_search_url": sold_url,
                    "notes": (
                        f"{len(card_results)} exact live listing(s); valuation from "
                        f"{candidate.source}."
                    ),
                }
            )
            logger.info(
                "MATCHED | %s exact listing(s) | %s in sniping window",
                len(card_results),
                sum(item.within_sniping_window for item in card_results),
            )

        excel.assess_results(all_results)
        result_by_item: dict[str, ListingResult] = {}
        for result in all_results:
            old = result_by_item.get(result.item_id)
            if old is None or result.score > old.score:
                result_by_item[result.item_id] = result
        results = sorted(
            result_by_item.values(),
            key=lambda item: (
                not item.queue_eligible,
                item.decision != "GREEN",
                item.decision == "RED",
                -item.long_term_score,
                -item.score,
                item.minutes_remaining,
            ),
        )[: int(config["maximum_result_rows"])]
        queue = [result for result in results if result.queue_eligible]

        excel.ensure_custom_result_sheets()
        excel.write_custom_live_results(results)
        excel.write_custom_live_queue(queue)
        run_id = "CUSTOM-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        excel.append_history(run_id, settings, attempts)
        long_term_update = excel.update_long_term_records(
            "CUSTOM LIVE",
            results,
            candidates,
        )
        logger.info(
            "LONG-TERM RECORDS | price snapshots=%s | portfolio rows refreshed=%s",
            long_term_update.get("snapshots", 0),
            long_term_update.get("portfolio_rows", 0),
        )
        excel.save()
        excel.close(save=True)
        excel = None
        os.replace(staging_path, workbook_path)
        committed = True

        green = sum(result.decision == "GREEN" for result in results)
        amber = sum(result.decision == "AMBER" for result in results)
        logger.info(
            "CUSTOM LIVE SCAN SUCCESSFUL | cards=%s results=%s queue=%s GREEN=%s AMBER=%s",
            len(candidates),
            len(results),
            len(queue),
            green,
            amber,
        )
        print()
        print("CUSTOM LIVE SCAN SUCCESSFUL")
        print(f"Input cards: {len(candidates)}")
        print(f"Matched live listings: {len(results)}")
        print(f"Custom Live Queue rows: {len(queue)}")
        print(f"GREEN: {green}")
        print(f"AMBER: {amber}")
        print(f"eBay API calls: {api_calls + item_detail_calls}")
        print("eBay Watchlist writes: DISABLED")
        return 0

    except KeyboardInterrupt:
        logger.warning("Interrupted by user; the workbook was not changed.")
        return 130
    except Exception as exc:
        logger.exception("CUSTOM LIVE SCAN FAILED: %s", exc)
        return 1
    finally:
        if client is not None:
            client.close()
        if excel is not None:
            excel.close(save=False)
        if not committed and staging_path.exists():
            try:
                staging_path.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
