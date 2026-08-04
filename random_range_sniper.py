from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from random_sniper.core import (
    Candidate,
    ListingResult,
    build_queries,
    confidence_label,
    decision_for,
    ebay_active_search_url,
    ebay_sold_search_url,
    eligible_candidates,
    listing_match_score,
    score_listing,
    select_candidates,
)
from random_sniper.ebay_client import EbayBrowseClient
from random_sniper.excel_adapter import ExcelAdapter


def configure_logging(root: Path) -> logging.Logger:
    logger = logging.getLogger("random-range-sniper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(
        root / "random-range-sniper.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Random market-range Pokémon eBay sniper."
    )
    parser.add_argument("--reroll-only", action="store_true")
    parser.add_argument("--test-api", action="store_true")
    return parser.parse_args()


def parse_money(value: Any) -> float:
    if not value:
        return 0.0
    if isinstance(value, dict):
        value = value.get("value", 0)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_end_time(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return (
            value
            if value.tzinfo
            else value.replace(tzinfo=timezone.utc)
        )
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def shipping_cost(item: dict[str, Any]) -> float:
    options = item.get("shippingOptions") or []
    costs = []
    for option in options:
        cost = option.get("shippingCost")
        if cost:
            costs.append(parse_money(cost))
    return min(costs) if costs else 0.0


def seller_fields(item: dict[str, Any]) -> tuple[str, float, int]:
    seller = item.get("seller") or {}
    username = str(seller.get("username", "") or "")
    try:
        percentage = float(seller.get("feedbackPercentage") or 0)
    except (TypeError, ValueError):
        percentage = 0.0
    try:
        count = int(seller.get("feedbackScore") or 0)
    except (TypeError, ValueError):
        count = 0
    return username, percentage, count


def item_url(item: dict[str, Any]) -> str:
    return str(
        item.get("itemWebUrl")
        or item.get("itemAffiliateWebUrl")
        or ""
    )


def image_url(item: dict[str, Any]) -> str:
    image = item.get("image") or {}
    return str(image.get("imageUrl") or "")


def evaluate_item(
    candidate: Candidate,
    item: dict[str, Any],
    query: str,
    settings,
    exclusions: list[str],
) -> ListingResult | None:
    title = str(item.get("title", "") or "")
    match_score, rejection = listing_match_score(
        candidate,
        title,
        exclusions,
    )
    if match_score < 0.52:
        return None

    current_bid = parse_money(item.get("currentBid") or item.get("price"))
    if current_bid <= 0:
        return None

    postage = shipping_cost(item)
    if (
        settings.maximum_postage is not None
        and postage > settings.maximum_postage
    ):
        return None

    delivered = current_bid + postage
    market = candidate.market_value
    ratio = delivered / market if market else 999
    target_delivered = market * settings.target_ratio
    maximum_bid = max(0.0, target_delivered - postage)
    headroom = maximum_bid - current_bid

    end_time = parse_end_time(item.get("itemEndDate"))
    minutes_remaining = max(
        0,
        int((end_time - datetime.now(timezone.utc)).total_seconds() / 60),
    )
    within_sniping_window = (
        minutes_remaining <= settings.ending_within_hours * 60
    )

    seller, feedback, feedback_count = seller_fields(item)
    try:
        bid_count = int(item.get("bidCount") or 0)
    except (TypeError, ValueError):
        bid_count = 0

    decision = decision_for(
        ratio=ratio,
        match_score=match_score,
        feedback_percent=feedback,
        minimum_feedback=settings.minimum_feedback,
        target_ratio=settings.target_ratio,
        headroom=headroom,
    )
    score = score_listing(
        ratio=ratio,
        match_score=match_score,
        feedback_percent=feedback,
        minutes_remaining=minutes_remaining,
        bid_count=bid_count,
        target_ratio=settings.target_ratio,
    )

    active_url = ebay_active_search_url(query)
    sold_url = ebay_sold_search_url(query)

    notes = rejection
    if feedback < settings.minimum_feedback:
        notes = (
            f"{notes}; " if notes else ""
        ) + "Seller feedback below configured target"
    if ratio > settings.target_ratio:
        notes = (
            f"{notes}; " if notes else ""
        ) + "Delivered cost exceeds configured target"
    if not within_sniping_window:
        notes = (
            f"{notes}; " if notes else ""
        ) + (
            "Live match found, but outside the configured sniping "
            f"window of {settings.ending_within_hours:g} hours"
        )

    return ListingResult(
        candidate=candidate,
        title=title,
        item_id=str(item.get("itemId", "") or ""),
        item_url=item_url(item),
        image_url=image_url(item),
        current_bid=round(current_bid, 2),
        postage=round(postage, 2),
        delivered=round(delivered, 2),
        market_value=round(market, 2),
        ratio=ratio,
        target_delivered=round(target_delivered, 2),
        maximum_bid=round(maximum_bid, 2),
        headroom=round(headroom, 2),
        end_time=end_time,
        minutes_remaining=minutes_remaining,
        within_sniping_window=within_sniping_window,
        bid_count=bid_count,
        seller=seller,
        feedback_percent=feedback,
        feedback_count=feedback_count,
        condition=str(item.get("condition", "") or ""),
        match_score=match_score,
        match_confidence=confidence_label(match_score),
        search_query=query,
        active_search_url=active_url,
        sold_search_url=sold_url,
        score=score,
        decision=decision,
        notes=notes,
    )


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    logger = configure_logging(root)

    load_dotenv(root / ".env", override=True, encoding="utf-8-sig")
    config = json.loads(
        (root / "random-sniper-config.json").read_text(encoding="utf-8")
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

    client = None
    excel = None

    try:
        if args.test_api:
            client = EbayBrowseClient(
                config,
                root / "data" / "random-range-sniper.sqlite",
            )
            result = client.test_connection()
            print("EBAY RANDOM SNIPER API CONNECTION SUCCESSFUL")
            print(f"Marketplace: {result['marketplace']}")
            print(f"Access token received: YES ({result['token_length']} characters)")
            return 0

        excel = ExcelAdapter(workbook_path)
        settings = excel.read_settings()
        candidates = excel.read_candidates()

        if settings.minimum_value > settings.maximum_value:
            raise RuntimeError(
                "Minimum market value cannot be greater than maximum."
            )

        now = datetime.now(timezone.utc)
        eligible = eligible_candidates(
            candidates,
            settings,
            now,
            int(config["vintage_cutoff_year"]),
            int(config["modern_start_year"]),
        )
        logger.info(
            "Eligible candidate pool: %s cards/variants between £%.2f and £%.2f",
            len(eligible),
            settings.minimum_value,
            settings.maximum_value,
        )

        if not eligible:
            raise RuntimeError(
                "No eligible cards matched the selected range and filters."
            )

        run_id = "RANDOM-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        exclusions = list(config["default_exclusions"])
        used_identities: set[str] = set()
        attempts: list[dict[str, Any]] = []
        all_results: list[ListingResult] = []
        api_calls = 0

        if args.reroll_only:
            selected = select_candidates(
                eligible,
                settings,
                count=settings.number_of_cards,
            )
            for candidate in selected:
                query = build_queries(candidate, settings.search_depth)[0]
                attempts.append(
                    {
                        "candidate": candidate,
                        "status": "READY TO SEARCH",
                        "queries_run": 0,
                        "listings_found": 0,
                        "results": [],
                        "best_result": None,
                        "target_ratio": settings.target_ratio,
                        "active_search_url": ebay_active_search_url(query),
                        "sold_search_url": ebay_sold_search_url(query),
                        "notes": "Rerolled without contacting eBay.",
                    }
                )
            excel.write_selected_cards(attempts)
            excel.update_kpis(
                run_id,
                len(eligible),
                attempts,
                [],
                [],
                0,
                "REROLL ONLY",
            )
            excel.append_history(run_id, settings, attempts)
            excel.save()
            logger.info("Reroll complete: %s cards selected.", len(attempts))
            return 0

        client = EbayBrowseClient(
            config,
            root / "data" / "random-range-sniper.sqlite",
        )

        desired_successful_cards = settings.number_of_cards
        successful_cards = 0
        total_attempt_limit = min(
            max(settings.maximum_attempts, settings.number_of_cards),
            len(eligible),
        )

        while (
            len(attempts) < total_attempt_limit
            and (
                successful_cards < desired_successful_cards
                if settings.replace_no_results
                else len(attempts) < settings.number_of_cards
            )
        ):
            next_pick = select_candidates(
                eligible,
                settings,
                count=1,
                exclude_identities=used_identities,
            )
            if not next_pick:
                break

            candidate = next_pick[0]
            used_identities.add(candidate.identity)
            queries = build_queries(candidate, settings.search_depth)
            exact_query = queries[0]
            active_url = ebay_active_search_url(exact_query)
            sold_url = ebay_sold_search_url(exact_query)

            logger.info(
                "Searching %s | %s | %s | %s (£%.2f)",
                candidate.name,
                candidate.set_name,
                candidate.number,
                candidate.variant,
                candidate.market_value,
            )

            card_results: list[ListingResult] = []
            seen_items: set[str] = set()

            for query in queries:
                items = client.search_auctions(query)
                api_calls += 1

                for item in items:
                    item_id = str(item.get("itemId", "") or "")
                    if not item_id or item_id in seen_items:
                        continue
                    seen_items.add(item_id)

                    evaluated = evaluate_item(
                        candidate,
                        item,
                        query,
                        settings,
                        exclusions,
                    )
                    if evaluated:
                        card_results.append(evaluated)

            card_results.sort(
                key=lambda item: (
                    item.decision != "GREEN",
                    item.decision == "RED",
                    -item.score,
                    item.minutes_remaining,
                )
            )
            all_results.extend(card_results)

            if card_results:
                successful_cards += 1
                status = "RESULTS FOUND"
                best_result = min(
                    card_results,
                    key=lambda item: item.ratio,
                )
                in_window_count = sum(
                    item.within_sniping_window
                    for item in card_results
                )
                notes = (
                    f"{len(card_results)} matched live auction(s); "
                    f"{in_window_count} inside the sniping window."
                )
            else:
                status = (
                    "REPLACED — NO RESULTS"
                    if settings.replace_no_results
                    else "NO RESULTS"
                )
                best_result = None
                notes = "No auction passed matching and configured filters."

            attempts.append(
                {
                    "candidate": candidate,
                    "status": status,
                    "queries_run": len(queries),
                    "listings_found": len(card_results),
                    "results": card_results,
                    "best_result": best_result,
                    "target_ratio": settings.target_ratio,
                    "active_search_url": active_url,
                    "sold_search_url": sold_url,
                    "notes": notes,
                }
            )

            logger.info(
                "Matched live listings: %s | In sniping window: %s",
                len(card_results),
                sum(item.within_sniping_window for item in card_results),
            )

        # Deduplicate identical eBay items found through different cards/queries,
        # keeping the highest-scoring match.
        result_by_item: dict[str, ListingResult] = {}
        for result in all_results:
            old = result_by_item.get(result.item_id)
            if old is None or result.score > old.score:
                result_by_item[result.item_id] = result

        all_results = sorted(
            result_by_item.values(),
            key=lambda item: (
                not item.within_sniping_window,
                item.decision != "GREEN",
                item.decision == "RED",
                -item.score,
                item.minutes_remaining,
            ),
        )[: int(config["maximum_result_rows"])]

        random_queue = sorted(
            [
                result
                for result in all_results
                if result.within_sniping_window
            ],
            key=lambda item: (
                item.decision != "GREEN",
                item.decision == "RED",
                -item.score,
                item.minutes_remaining,
            ),
        )

        excel.write_selected_cards(attempts)
        excel.write_results(all_results)
        excel.write_random_snipe_queue(random_queue)
        excel.append_history(run_id, settings, attempts)
        excel.update_kpis(
            run_id,
            len(eligible),
            attempts,
            all_results,
            random_queue,
            api_calls,
            "LIVE EBAY SCAN",
        )

        copied = 0
        if settings.copy_green_to_main_queue:
            copied = excel.copy_green_to_snipe_queue(random_queue)

        excel.save()

        logger.info("Random Range Sniper completed successfully.")
        logger.info("Cards attempted: %s", len(attempts))
        logger.info("Cards with matched auctions: %s", successful_cards)
        logger.info("Total matched live listings: %s", len(all_results))
        logger.info("Random Snipe Queue rows: %s", len(random_queue))
        logger.info(
            "Queue GREEN: %s | AMBER: %s | RED: %s",
            sum(item.decision == "GREEN" for item in random_queue),
            sum(item.decision == "AMBER" for item in random_queue),
            sum(item.decision == "RED" for item in random_queue),
        )
        logger.info("eBay API search calls: %s", api_calls)
        logger.info("GREEN rows copied to Snipe Queue: %s", copied)
        print()
        print("RANDOM RANGE SNIPER SUCCESSFUL")
        print(f"Run ID: {run_id}")
        print(f"Cards attempted: {len(attempts)}")
        print(f"Cards with results: {successful_cards}")
        print(f"Matched live listings: {len(all_results)}")
        print(f"Random Snipe Queue rows: {len(random_queue)}")
        print(
            "Queue GREEN opportunities: "
            f"{sum(item.decision == 'GREEN' for item in random_queue)}"
        )
        return 0

    finally:
        if client is not None:
            client.close()
        if excel is not None:
            excel.close(save=True)


if __name__ == "__main__":
    raise SystemExit(main())
