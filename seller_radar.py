from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from ebay_watchlist import sync_green_results
from random_range_sniper import (
    enrich_result_condition,
    evaluate_item,
    image_url,
    item_url,
    parse_end_time,
    parse_money,
    seller_fields,
    shipping_cost,
)
from random_sniper.core import (
    ListingResult,
    build_queries,
    normalize_text,
)
from random_sniper.seller_discovery import (
    CandidateTitleMatcher,
)
from seller_radar_client import SellerRadarClient
from seller_radar_excel import SellerRadarExcelAdapter
from seller_radar_history import SellerRadarHistory


DEFAULT_LISTING_COUNT = 50
MAXIMUM_LISTING_COUNT = 1000


def configure_logging(root: Path) -> logging.Logger:
    logger = logging.getLogger("seller-radar")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(
        root / "seller-radar.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyse active Pokémon listings belonging to one eBay seller."
        )
    )
    parser.add_argument(
        "--seller",
        required=True,
        help="Exact eBay username.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LISTING_COUNT,
        help="Maximum listings to fetch, 1-1000.",
    )
    return parser.parse_args()


def safe_limit(value: int) -> int:
    return max(
        1,
        min(int(value), MAXIMUM_LISTING_COUNT),
    )


def listing_type(item: dict[str, Any]) -> str:
    options = {
        str(value).strip().upper()
        for value in item.get("buyingOptions") or []
        if str(value).strip()
    }
    if options == {"AUCTION", "FIXED_PRICE"}:
        return "AUCTION + BUY IT NOW"
    if "AUCTION" in options:
        return "AUCTION"
    if "FIXED_PRICE" in options:
        return "BUY IT NOW"
    if "BEST_OFFER" in options:
        return "BEST OFFER"
    return "OTHER"


def displayed_price(item: dict[str, Any]) -> float:
    bid = parse_money(item.get("currentBidPrice"))
    if bid > 0:
        return bid
    return parse_money(item.get("price"))


def excluded_reason(
    title: str,
    exclusions: list[str],
) -> str:
    normalized = normalize_text(title)
    for value in exclusions:
        term = normalize_text(value)
        if term and term in normalized:
            return f"Excluded term: {value}"
    return ""


def unmatched_row(
    item: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "title": str(item.get("title", "") or ""),
        "item_id": str(item.get("itemId", "") or ""),
        "listing_type": listing_type(item),
        "price": displayed_price(item),
        "postage": shipping_cost(item),
        "end_time": parse_end_time(
            item.get("itemEndDate")
        ).replace(tzinfo=None),
        "reason": reason,
        "item_url": item_url(item),
    }


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    logger = configure_logging(root)

    seller = str(args.seller or "").strip()
    if not seller:
        raise RuntimeError(
            "An eBay seller username is required."
        )
    requested = safe_limit(args.limit)

    load_dotenv(
        root / ".env",
        override=True,
        encoding="utf-8-sig",
    )
    config = json.loads(
        (root / "random-sniper-config.json")
        .read_text(encoding="utf-8")
    )

    workbook_path = Path(
        os.getenv(
            "WORKBOOK_PATH",
            "Pokemon-Auction-Scanner-Dashboard.xlsx",
        )
    )
    if not workbook_path.is_absolute():
        workbook_path = root / workbook_path

    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Workbook not found: {workbook_path}"
        )

    excel = None
    client = None

    try:
        logger.info(
            "SELLER RADAR START | seller=%s | listing cap=%s",
            seller,
            requested,
        )
        logger.info(
            "Opening Excel and loading the market database..."
        )

        excel = SellerRadarExcelAdapter(
            workbook_path
        )
        settings = excel.read_settings()
        candidates = excel.read_candidates()

        # Seller Radar should evaluate every price-bearing card found rather
        # than hide listings merely because the Random Sniper's postage cap
        # is restrictive.
        radar_settings = copy.copy(settings)
        radar_settings.maximum_postage = None
        radar_settings.listing_formats = (
            "Auctions + Buy It Now"
        )
        radar_settings.expand_green_sellers = False

        logger.info(
            "Market database ready: %s priced card variants.",
            len(candidates),
        )
        logger.info(
            "Analysis target: %.1f%% of market | minimum feedback %.1f%%.",
            radar_settings.target_ratio * 100,
            radar_settings.minimum_feedback,
        )

        matcher = CandidateTitleMatcher(candidates)
        exclusions = list(config["default_exclusions"])

        history = SellerRadarHistory(
            root / "data" / "seller-radar-scan-history.json"
        )
        seen_item_ids = history.seen_item_ids(seller)
        previously_scanned = len(seen_item_ids)
        batch_number = history.completed_run_count(seller) + 1

        logger.info(
            "Seller history: %s listing ID(s) previously scanned | "
            "next batch=%s.",
            previously_scanned,
            batch_number,
        )

        client = SellerRadarClient(
            config,
            lambda message: logger.info(message),
        )

        batch = client.search_next_unseen_inventory(
            seller=seller,
            requested_count=requested,
            seen_item_ids=seen_item_ids,
            query=os.getenv(
                "SELLER_RADAR_QUERY",
                "pokemon",
            ).strip() or "pokemon",
        )
        items = batch.items

        logger.info(
            "FETCH COMPLETE | selected unseen=%s | examined=%s | "
            "skipped previously scanned=%s | pages=%s.",
            len(items),
            batch.listings_examined,
            batch.skipped_previously_scanned,
            batch.pages_scanned,
        )

        if not items:
            print()
            print("SELLER RADAR — NO UNSCANNED ACTIVE LISTINGS")
            print(f"Seller: {seller}")
            print(
                f"Previously scanned listing IDs: "
                f"{previously_scanned}"
            )
            print(
                f"Active listings examined this run: "
                f"{batch.listings_examined}"
            )
            print(
                f"Previously scanned listings skipped: "
                f"{batch.skipped_previously_scanned}"
            )
            if batch.inventory_exhausted:
                print(
                    "All currently API-visible Pokémon listings for "
                    "this seller have already been scanned."
                )
            elif batch.page_limit_reached:
                print(
                    "No unseen listing was found before the configured "
                    "page-safety limit."
                )
            print(
                "The existing seller worksheet was left unchanged."
            )
            return 0
        logger.info(
            "IDENTIFICATION STAGE | matching titles against the local "
            "card database."
        )

        results: list[ListingResult] = []
        unmatched: list[dict[str, Any]] = []
        outcomes: dict[str, dict[str, Any]] = {}
        detail_limit = max(
            0,
            int(
                os.getenv(
                    "SELLER_RADAR_MAX_CONDITION_CHECKS",
                    str(min(requested, 50)),
                )
            ),
        )
        detail_checks = 0

        for index, item in enumerate(items, start=1):
            if (
                index == 1
                or index % 10 == 0
                or index == len(items)
            ):
                logger.info(
                    "Identification progress: %s/%s.",
                    index,
                    len(items),
                )

            title = str(item.get("title", "") or "")
            exclusion = excluded_reason(
                title,
                exclusions,
            )
            if exclusion:
                unmatched.append(
                    unmatched_row(item, exclusion)
                )
                outcomes[
                    str(item.get("itemId", "") or "")
                ] = {
                    "matched": False,
                    "decision": "",
                    "reason": exclusion,
                    "listing_type": listing_type(item),
                }
                continue

            candidate = matcher.match(
                title,
                exclusions,
            )
            if candidate is None:
                reason = (
                    "No high-confidence exact card-name and "
                    "card-number match in the priced database"
                )
                unmatched.append(
                    unmatched_row(
                        item,
                        reason,
                    )
                )
                outcomes[
                    str(item.get("itemId", "") or "")
                ] = {
                    "matched": False,
                    "decision": "",
                    "reason": reason,
                    "listing_type": listing_type(item),
                }
                continue

            query = build_queries(
                candidate,
                "Fast",
            )[0]
            evaluated = evaluate_item(
                candidate,
                item,
                query,
                radar_settings,
                exclusions,
            )
            if evaluated is None:
                reason = (
                    "The card was identified, but price or "
                    "listing data was insufficient for evaluation"
                )
                unmatched.append(
                    unmatched_row(
                        item,
                        reason,
                    )
                )
                outcomes[
                    str(item.get("itemId", "") or "")
                ] = {
                    "matched": True,
                    "decision": "",
                    "reason": reason,
                    "listing_type": listing_type(item),
                }
                continue

            evaluated.discovery_source = (
                f"SELLER RADAR: {seller}"
            )

            if (
                evaluated.decision in {"GREEN", "AMBER"}
                and detail_checks < detail_limit
            ):
                logger.info(
                    "Condition check %s/%s | %s",
                    detail_checks + 1,
                    detail_limit,
                    evaluated.title[:90],
                )
                if enrich_result_condition(
                    evaluated,
                    item,
                    client,
                    logger,
                ):
                    detail_checks += 1

            results.append(evaluated)
            outcomes[evaluated.item_id] = {
                "matched": True,
                "decision": evaluated.decision,
                "reason": "",
                "listing_type": evaluated.listing_type,
            }

        # Remove duplicates defensively and keep the strongest card match.
        deduplicated: dict[str, ListingResult] = {}
        for result in results:
            old = deduplicated.get(result.item_id)
            if (
                old is None
                or result.match_score > old.match_score
            ):
                deduplicated[result.item_id] = result

        results = list(deduplicated.values())
        decision_order = {
            "GREEN": 0,
            "AMBER": 1,
            "RED": 2,
        }
        results.sort(
            key=lambda result: (
                decision_order.get(
                    result.decision,
                    3,
                ),
                result.ratio,
                result.minutes_remaining,
                -result.score,
            )
        )

        green = sum(
            result.decision == "GREEN"
            for result in results
        )
        amber = sum(
            result.decision == "AMBER"
            for result in results
        )
        red = sum(
            result.decision == "RED"
            for result in results
        )

        logger.info(
            "ANALYSIS COMPLETE | matched=%s | GREEN=%s | "
            "AMBER=%s | RED=%s | unmatched=%s",
            len(results),
            green,
            amber,
            red,
            len(unmatched),
        )

        watchlist_summary = sync_green_results(
            results,
            root=root,
            source=f"SELLER RADAR: {seller}",
            logger=logger,
        )

        summary = {
            "seller": seller,
            "last_scan": datetime.now(),
            "requested": requested,
            "fetched": len(items),
            "matched": len(results),
            "green": green,
            "amber": amber,
            "red": red,
            "unmatched": len(unmatched),
            "search_calls": client.search_calls,
            "detail_calls": client.detail_calls,
            "total_calls": client.total_api_calls,
            "target_ratio": radar_settings.target_ratio,
            "watchlist": watchlist_summary.display,
            "batch_number": batch_number,
            "previously_scanned": previously_scanned,
            "new_batch": len(items),
            "listings_examined": batch.listings_examined,
            "skipped_seen": batch.skipped_previously_scanned,
            "history_after": previously_scanned + len(items),
            "inventory_status": (
                "Current active inventory exhausted"
                if batch.inventory_exhausted
                else "More unseen listings may remain"
            ),
        }

        logger.info(
            "WRITING EXCEL | creating or refreshing the seller tab..."
        )
        sheet_name = excel.write_seller_radar(
            seller=seller,
            results=results,
            unmatched=unmatched,
            summary=summary,
        )
        excel.save()

        run_id = (
            f"SELLER-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        recorded = history.record_batch(
            seller=seller,
            items=items,
            outcomes=outcomes,
            run_summary={
                "run_id": run_id,
                "batch_number": batch_number,
                "requested": requested,
                "selected_unseen": len(items),
                "pages_scanned": batch.pages_scanned,
                "listings_examined": batch.listings_examined,
                "skipped_previously_scanned":
                    batch.skipped_previously_scanned,
                "reported_total": batch.reported_total,
                "inventory_exhausted": batch.inventory_exhausted,
                "matched": len(results),
                "unmatched": len(unmatched),
                "green": green,
                "amber": amber,
                "red": red,
                "worksheet": sheet_name,
            },
        )
        history.save()
        history_total = history.scanned_count(seller)

        logger.info(
            "Seller history saved: %s new item ID(s); "
            "%s total for this seller.",
            recorded,
            history_total,
        )
        logger.info(
            "SELLER RADAR SUCCESSFUL | sheet=%s",
            sheet_name,
        )

        print()
        print("SELLER RADAR SUCCESSFUL")
        print(f"Seller: {seller}")
        print(f"Worksheet: {sheet_name}")
        print(f"Batch number: {batch_number}")
        print(f"Requested unseen listings: {requested}")
        print(f"Previously scanned before this run: {previously_scanned}")
        print(f"New unseen listings selected: {len(items)}")
        print(
            f"API-visible listings examined: "
            f"{batch.listings_examined}"
        )
        print(
            f"Previously scanned listings skipped: "
            f"{batch.skipped_previously_scanned}"
        )
        print(f"Search pages used: {batch.pages_scanned}")
        print(f"Seller history total after run: {history_total}")
        print(f"Exact card matches: {len(results)}")
        print(f"GREEN: {green}")
        print(f"AMBER: {amber}")
        print(f"RED: {red}")
        print(f"Unmatched/manual review: {len(unmatched)}")
        print(
            f"eBay API calls: {client.total_api_calls} "
            f"(search {client.search_calls}, "
            f"details {client.detail_calls}, "
            f"OAuth {client.oauth_calls})"
        )
        print(
            f"eBay Watchlist: {watchlist_summary.display}"
        )
        return 0

    except KeyboardInterrupt:
        logger.warning(
            "Interrupted by user. Releasing the hidden Excel process..."
        )
        return 130

    except Exception as exc:
        logger.exception(
            "SELLER RADAR FAILED: %s",
            exc,
        )
        return 1

    finally:
        if client is not None:
            client.close()
        if excel is not None:
            excel.close(save=True)


if __name__ == "__main__":
    raise SystemExit(main())
