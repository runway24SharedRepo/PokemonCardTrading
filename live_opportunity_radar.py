from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from live_radar.condition import assess_condition
from live_radar.core import (
    Candidate,
    CandidateTitleMatcher,
    RadarResult,
    RadarSettings,
    confidence_label,
    decision_for,
    ebay_direct_search_url,
    ebay_sold_search_url,
    exact_card_query,
    score_listing,
    within_time_window,
)
from live_radar.ebay_client import (
    ApiBudget,
    EbayBrowseClient,
)
from live_radar.excel_adapter import ExcelAdapter
from ebay_watchlist import sync_green_results


def configure_logging(root: Path) -> logging.Logger:
    logger = logging.getLogger("live-opportunity-radar")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(
        root / "live-radar.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Broad Pokémon auction radar for listings ending soon."
        )
    )
    parser.add_argument(
        "--test-api",
        action="store_true",
    )
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
    return datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )


def shipping_cost(item: dict[str, Any]) -> float:
    costs = []
    for option in item.get("shippingOptions") or []:
        cost = option.get("shippingCost")
        if cost:
            costs.append(parse_money(cost))
    return min(costs) if costs else 0.0


def seller_fields(
    item: dict[str, Any],
) -> tuple[str, float, int]:
    seller = item.get("seller") or {}
    username = str(seller.get("username", "") or "")
    try:
        percentage = float(
            seller.get("feedbackPercentage") or 0
        )
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


def listing_image_url(item: dict[str, Any]) -> str:
    return str(
        (item.get("image") or {}).get("imageUrl")
        or ""
    )


def evaluate_listing(
    candidate: Candidate,
    match_score: float,
    item: dict[str, Any],
    settings: RadarSettings,
    condition_display: str,
    condition_flag: str,
    condition_details: str,
    *,
    discovery_source: str,
    parent_item_id: str = "",
) -> RadarResult | None:
    options = {
        str(value).strip().upper()
        for value in (item.get("buyingOptions") or [])
        if str(value).strip()
    }
    if options and "AUCTION" not in options:
        return None

    current_bid = parse_money(item.get("currentBidPrice"))
    if current_bid <= 0:
        current_bid = parse_money(item.get("price"))
    if current_bid <= 0:
        return None

    postage = shipping_cost(item)
    delivered = current_bid + postage

    if delivered > settings.maximum_delivered_cost:
        return None
    if candidate.market_value < settings.minimum_market_value:
        return None

    target_delivered = (
        candidate.market_value * settings.target_ratio
    )
    maximum_bid = max(
        0.0,
        target_delivered - postage,
    )
    headroom = maximum_bid - current_bid
    ratio = (
        delivered / candidate.market_value
        if candidate.market_value
        else 999.0
    )

    end_time = parse_end_time(item.get("itemEndDate"))
    minutes_remaining = int(
        (end_time - datetime.now(timezone.utc))
        .total_seconds()
        / 60
    )
    if not within_time_window(
        minutes_remaining,
        settings,
    ):
        return None

    seller, feedback, feedback_count = seller_fields(item)
    try:
        bid_count = int(item.get("bidCount") or 0)
    except (TypeError, ValueError):
        bid_count = 0

    decision = decision_for(
        ratio=ratio,
        match_score=match_score,
        feedback_percent=feedback,
        feedback_count=feedback_count,
        settings=settings,
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

    if decision == "GREEN":
        action = (
            "BID NOW"
            if minutes_remaining <= 5
            else "WATCH / BID"
        )
    elif decision == "AMBER":
        action = "REVIEW"
    else:
        action = "SKIP"

    exact_query = exact_card_query(candidate)
    notes: list[str] = []

    if condition_flag == "RED":
        notes.append(
            "CONDITION RED — financial decision unchanged; "
            "inspect every photograph."
        )
    if feedback < settings.minimum_feedback:
        notes.append(
            "Seller feedback below configured target."
        )
    if ratio > settings.target_ratio:
        notes.append(
            "Current delivered cost is above the GREEN target."
        )
    if minutes_remaining <= 5:
        notes.append("LAST-MINUTE AUCTION.")

    return RadarResult(
        candidate=candidate,
        title=str(item.get("title", "") or ""),
        item_id=str(item.get("itemId", "") or ""),
        item_url=item_url(item),
        listing_image_url=listing_image_url(item),
        current_bid=round(current_bid, 2),
        postage=round(postage, 2),
        delivered=round(delivered, 2),
        market_value=round(candidate.market_value, 2),
        ratio=ratio,
        target_delivered=round(target_delivered, 2),
        maximum_bid=round(maximum_bid, 2),
        bid_headroom=round(headroom, 2),
        decision=decision,
        recommended_action=action,
        score=score,
        end_time=end_time,
        minutes_remaining=minutes_remaining,
        bid_count=bid_count,
        seller=seller,
        feedback_percent=feedback,
        feedback_count=feedback_count,
        condition=condition_display,
        condition_flag=condition_flag,
        condition_details=condition_details,
        match_score=match_score,
        match_confidence=confidence_label(match_score),
        search_query=exact_query,
        direct_search_url=ebay_direct_search_url(
            exact_query
        ),
        sold_search_url=ebay_sold_search_url(
            exact_query
        ),
        discovery_source=discovery_source,
        parent_item_id=parent_item_id,
        notes=" ".join(notes),
    )


def group_by_green_seller(
    primary: list[RadarResult],
    discoveries: list[RadarResult],
) -> list[RadarResult]:
    by_seller: dict[str, list[RadarResult]] = defaultdict(list)
    for result in discoveries:
        by_seller[result.seller.casefold()].append(result)

    for values in by_seller.values():
        values.sort(
            key=lambda item: (
                item.decision != "GREEN",
                item.minutes_remaining,
                -item.score,
            )
        )

    output: list[RadarResult] = []
    inserted: set[str] = set()

    for result in primary:
        output.append(result)
        key = result.seller.casefold()

        if (
            result.decision == "GREEN"
            and key
            and key not in inserted
        ):
            output.extend(by_seller.get(key, []))
            inserted.add(key)

    return output


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    logger = configure_logging(root)

    load_dotenv(
        root / ".env",
        override=True,
        encoding="utf-8-sig",
    )
    config = json.loads(
        (root / "live-radar-config.json")
        .read_text(encoding="utf-8")
    )

    config["marketplace_id"] = os.getenv(
        "EBAY_MARKETPLACE_ID",
        config["marketplace_id"],
    ).strip()
    config["delivery_country"] = os.getenv(
        "EBAY_DELIVERY_COUNTRY",
        config["delivery_country"],
    ).strip()
    config["item_location_country"] = os.getenv(
        "EBAY_ITEM_LOCATION_COUNTRY",
        config["item_location_country"],
    ).strip()

    workbook_path = Path(
        os.getenv(
            "WORKBOOK_PATH",
            "Pokemon-Auction-Scanner-Dashboard.xlsx",
        )
    )
    if not workbook_path.is_absolute():
        workbook_path = root / workbook_path

    excel = None
    client = None

    broad_requests = 0
    raw_count = 0
    unique_count = 0
    seller_searches = 0
    condition_checks = 0

    try:
        if not workbook_path.exists():
            raise FileNotFoundError(
                f"Workbook not found: {workbook_path}"
            )

        excel = ExcelAdapter(workbook_path)
        settings = excel.read_settings()

        if not settings.enabled:
            logger.info(
                "Scanner Settings → Enabled is NO. Nothing was changed."
            )
            return 0

        logger.info(
            "Loading full market database from Excel..."
        )
        candidates = excel.read_candidates()
        matcher = CandidateTitleMatcher(candidates)

        logger.info(
            "Market database ready: %s priced card variants.",
            len(candidates),
        )
        logger.info(
            "Radar window: %s minutes to %.1f hours.",
            settings.minimum_minutes_remaining,
            settings.maximum_hours_remaining,
        )
        logger.info(
            "Broad request cap: %s; %s results/request; "
            "total API-call cap: %s.",
            settings.maximum_broad_requests,
            settings.results_per_request,
            settings.maximum_total_api_calls,
        )

        budget = ApiBudget(
            settings.maximum_total_api_calls
        )
        client = EbayBrowseClient(
            os.getenv("EBAY_CLIENT_ID", "").strip(),
            os.getenv("EBAY_CLIENT_SECRET", "").strip(),
            config,
            budget,
            lambda message: logger.info(message),
        )

        if args.test_api:
            logger.info(
                "Testing eBay connection with one broad radar request..."
            )
            items = client.broad_auction_page(
                settings.broad_query,
                settings.minimum_minutes_remaining,
                settings.maximum_hours_remaining,
                min(settings.results_per_request, 5),
                0,
            )
            logger.info(
                "API connection successful; %s sample result(s).",
                len(items),
            )
            return 0

        exclusions = list(config["default_exclusions"])
        broad_items: dict[str, dict[str, Any]] = {}

        for request_number in range(
            1,
            settings.maximum_broad_requests + 1,
        ):
            offset = (
                request_number - 1
            ) * settings.results_per_request

            logger.info(
                "BROAD SEARCH %s/%s | query='%s' | offset=%s | "
                "API calls %s/%s",
                request_number,
                settings.maximum_broad_requests,
                settings.broad_query,
                offset,
                budget.used,
                budget.maximum_calls,
            )

            items = client.broad_auction_page(
                settings.broad_query,
                settings.minimum_minutes_remaining,
                settings.maximum_hours_remaining,
                settings.results_per_request,
                offset,
            )
            broad_requests += 1
            raw_count += len(items)

            for item in items:
                item_id = str(item.get("itemId", "") or "")
                if item_id:
                    broad_items[item_id] = item

            logger.info(
                "Returned %s listing(s); %s unique accumulated.",
                len(items),
                len(broad_items),
            )

            if len(items) < settings.results_per_request:
                logger.info(
                    "No additional broad page is required."
                )
                break

        unique_count = len(broad_items)
        logger.info(
            "IDENTIFICATION STAGE | analysing %s unique auction title(s).",
            unique_count,
        )

        matched: list[
            tuple[
                Candidate,
                float,
                dict[str, Any],
            ]
        ] = []

        for index, item in enumerate(
            broad_items.values(),
            start=1,
        ):
            if index == 1 or index % 50 == 0:
                logger.info(
                    "Card identification progress: %s/%s.",
                    index,
                    unique_count,
                )

            candidate, score, _ = matcher.match(
                str(item.get("title", "") or ""),
                exclusions,
            )
            if candidate is not None:
                matched.append(
                    (candidate, score, item)
                )

        logger.info(
            "Exact database matches: %s/%s.",
            len(matched),
            unique_count,
        )

        primary_results: list[RadarResult] = []

        for index, (
            candidate,
            match_score,
            item,
        ) in enumerate(matched, start=1):
            summary_condition = assess_condition(item)
            condition = summary_condition

            # Detailed condition calls are deliberately reserved for listings
            # that look financially capable of becoming GREEN/AMBER.
            provisional = evaluate_listing(
                candidate,
                match_score,
                item,
                settings,
                summary_condition.display,
                summary_condition.flag,
                summary_condition.details,
                discovery_source="BROAD RADAR",
            )
            if provisional is None:
                continue

            if (
                provisional.decision in {"GREEN", "AMBER"}
                and condition_checks
                < settings.maximum_condition_checks
                and budget.remaining > 0
            ):
                try:
                    detail = client.get_item_details(
                        provisional.item_id
                    )
                    condition_checks += 1
                    condition = assess_condition(
                        item,
                        detail,
                    )
                except Exception as exc:
                    logger.warning(
                        "Detailed condition unavailable for %s: %s",
                        provisional.item_id,
                        exc,
                    )

            final = evaluate_listing(
                candidate,
                match_score,
                item,
                settings,
                condition.display,
                condition.flag,
                condition.details,
                discovery_source="BROAD RADAR",
            )
            if (
                final is not None
                and final.decision in {"GREEN", "AMBER"}
            ):
                primary_results.append(final)

        excel.assess_results(primary_results)
        primary_results.sort(
            key=lambda result: (
                result.decision != "GREEN",
                -result.long_term_score,
                result.minutes_remaining,
                -result.score,
            )
        )

        logger.info(
            "VALUED OPPORTUNITIES | GREEN=%s | AMBER=%s.",
            sum(
                result.decision == "GREEN"
                for result in primary_results
            ),
            sum(
                result.decision == "AMBER"
                for result in primary_results
            ),
        )

        seller_discoveries: list[RadarResult] = []

        if settings.expand_green_sellers:
            anchors: list[RadarResult] = []
            seen_sellers: set[str] = set()

            for result in primary_results:
                key = result.seller.casefold()
                if (
                    result.decision == "GREEN"
                    and key
                    and key not in seen_sellers
                ):
                    seen_sellers.add(key)
                    anchors.append(result)

            anchors = anchors[
                : settings.maximum_green_sellers
            ]

            logger.info(
                "SELLER EXPANSION | %s GREEN seller(s) selected.",
                len(anchors),
            )

            known_item_ids = {
                result.item_id
                for result in primary_results
            }

            for seller_index, anchor in enumerate(
                anchors,
                start=1,
            ):
                if budget.remaining <= 0:
                    logger.warning(
                        "API cap reached; remaining seller expansion skipped."
                    )
                    break

                logger.info(
                    "GREEN SELLER %s/%s | %s | checking up to %s listings.",
                    seller_index,
                    len(anchors),
                    anchor.seller,
                    settings.seller_listing_limit,
                )

                try:
                    items = client.seller_auction_page(
                        anchor.seller,
                        config["seller_search_query"],
                        settings.minimum_minutes_remaining,
                        settings.maximum_hours_remaining,
                        settings.seller_listing_limit,
                    )
                    seller_searches += 1
                except Exception as exc:
                    logger.warning(
                        "Seller expansion failed for %s: %s",
                        anchor.seller,
                        exc,
                    )
                    continue

                found_for_seller: list[RadarResult] = []

                for item in items:
                    item_id = str(
                        item.get("itemId", "") or ""
                    )
                    if (
                        not item_id
                        or item_id in known_item_ids
                    ):
                        continue

                    candidate, match_score, _ = matcher.match(
                        str(item.get("title", "") or ""),
                        exclusions,
                    )
                    if candidate is None:
                        continue

                    condition = assess_condition(item)
                    provisional = evaluate_listing(
                        candidate,
                        match_score,
                        item,
                        settings,
                        condition.display,
                        condition.flag,
                        condition.details,
                        discovery_source="↳ SAME SELLER",
                        parent_item_id=anchor.item_id,
                    )
                    if (
                        provisional is None
                        or provisional.decision
                        not in {"GREEN", "AMBER"}
                    ):
                        continue

                    if (
                        condition_checks
                        < settings.maximum_condition_checks
                        and budget.remaining > 0
                    ):
                        try:
                            detail = client.get_item_details(
                                provisional.item_id
                            )
                            condition_checks += 1
                            condition = assess_condition(
                                item,
                                detail,
                            )
                        except Exception as exc:
                            logger.warning(
                                "Detailed condition unavailable for %s: %s",
                                provisional.item_id,
                                exc,
                            )

                    final = evaluate_listing(
                        candidate,
                        match_score,
                        item,
                        settings,
                        condition.display,
                        condition.flag,
                        condition.details,
                        discovery_source="↳ SAME SELLER",
                        parent_item_id=anchor.item_id,
                    )
                    if (
                        final is not None
                        and final.decision
                        in {"GREEN", "AMBER"}
                    ):
                        found_for_seller.append(final)
                        known_item_ids.add(final.item_id)

                excel.assess_results(found_for_seller)
                found_for_seller.sort(
                    key=lambda result: (
                        result.decision != "GREEN",
                        -result.long_term_score,
                        result.minutes_remaining,
                        -result.score,
                    )
                )
                found_for_seller = found_for_seller[
                    : settings.opportunities_per_seller
                ]
                seller_discoveries.extend(found_for_seller)

                logger.info(
                    "Seller %s produced %s additional opportunity/opportunities.",
                    anchor.seller,
                    len(found_for_seller),
                )

        final_results = group_by_green_seller(
            primary_results,
            seller_discoveries,
        )[: settings.maximum_live_rows]

        watchlist_summary = sync_green_results(
            final_results,
            root=root,
            source="LIVE RADAR",
            logger=logger,
        )

        logger.info(
            "WRITING EXCEL | %s live opportunity row(s).",
            len(final_results),
        )

        archived = 0
        if settings.archive_previous_results:
            archived = excel.archive_current_live_results()
            logger.info(
                "Archived %s previous live row(s).",
                archived,
            )

        excel.write_results(final_results)
        excel.update_dashboard(final_results)

        green = sum(
            result.decision == "GREEN"
            for result in final_results
        )
        amber = sum(
            result.decision == "AMBER"
            for result in final_results
        )

        excel.append_log(
            broad_requests=broad_requests,
            raw_results=raw_count,
            unique_results=unique_count,
            green=green,
            amber=amber,
            message=(
                f"Radar complete: {len(final_results)} opportunities; "
                f"{len(seller_discoveries)} same-seller discoveries; "
                f"{condition_checks} detailed condition checks; "
                f"{budget.used}/{budget.maximum_calls} API calls."
            ),
        )
        long_term_update = excel.update_long_term_records(
            "LIVE RADAR",
            final_results,
            candidates,
        )
        logger.info(
            "Long-term records | price snapshots=%s | portfolio rows refreshed=%s",
            long_term_update.get("snapshots", 0),
            long_term_update.get("portfolio_rows", 0),
        )
        excel.save()

        logger.info("LIVE OPPORTUNITY RADAR SUCCESSFUL.")
        logger.info(
            "Summary | raw=%s unique=%s exact-matched=%s "
            "output=%s GREEN=%s AMBER=%s",
            raw_count,
            unique_count,
            len(matched),
            len(final_results),
            green,
            amber,
        )
        logger.info(
            "API calls used: %s/%s | seller searches=%s | "
            "condition checks=%s",
            budget.used,
            budget.maximum_calls,
            seller_searches,
            condition_checks,
        )

        print()
        print("LIVE OPPORTUNITY RADAR SUCCESSFUL")
        print(f"Broad search requests: {broad_requests}")
        print(f"Raw auction listings: {raw_count}")
        print(f"Unique auction listings: {unique_count}")
        print(f"Exact card matches: {len(matched)}")
        print(f"Live opportunity rows: {len(final_results)}")
        print(f"GREEN: {green}")
        print(f"AMBER: {amber}")
        print(
            "Strong long-term opportunities (score 80+): "
            f"{sum(result.long_term_score >= 80 for result in final_results)}"
        )
        print(
            "Same-seller opportunities: "
            f"{len(seller_discoveries)}"
        )
        print(
            f"API calls: {budget.used}/"
            f"{budget.maximum_calls}"
        )
        print(f"eBay Watchlist: {watchlist_summary.display}")
        return 0

    except KeyboardInterrupt:
        logger.warning(
            "Interrupted by user. Releasing the hidden Excel process..."
        )
        if excel is not None:
            try:
                excel.append_log(
                    broad_requests,
                    raw_count,
                    unique_count,
                    0,
                    0,
                    "Run interrupted by user; no completed result set saved.",
                    success=False,
                )
            except Exception:
                pass
        return 130

    except Exception as exc:
        logger.exception("LIVE RADAR FAILED: %s", exc)
        if excel is not None:
            try:
                excel.append_log(
                    broad_requests,
                    raw_count,
                    unique_count,
                    0,
                    0,
                    repr(exc),
                    success=False,
                )
                excel.save()
            except Exception:
                pass
        return 1

    finally:
        if excel is not None:
            excel.close(save=True)


if __name__ == "__main__":
    raise SystemExit(main())
