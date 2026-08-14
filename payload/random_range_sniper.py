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
    ebay_auction_search_url,
    ebay_buy_now_search_url,
    ebay_sold_search_url,
    eligible_candidates,
    listing_match_score,
    score_listing,
    overall_decision,
    recommended_action,
    select_candidates,
)
from random_sniper.condition import assess_condition
from random_sniper.ebay_client import EbayBrowseClient
from random_sniper.excel_adapter import ExcelAdapter
from random_sniper.seller_discovery import (
    CandidateTitleMatcher,
    group_queue_results,
)
from on_demand_pricing import OnDemandPriceResolver


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
    condition_assessment = assess_condition(item)
    match_score, rejection = listing_match_score(
        candidate,
        title,
        exclusions,
    )
    if match_score < 0.52:
        return None

    options = tuple(
        sorted(
            {
                str(value).strip().upper()
                for value in (item.get("buyingOptions") or [])
                if str(value).strip()
            }
        )
    )
    option_set = set(options)

    # eBay's documented auction field is currentBidPrice. The generic price
    # field is used for a fixed-price/Buy It Now option.
    current_bid = (
        parse_money(item.get("currentBidPrice"))
        if "AUCTION" in option_set
        else 0.0
    )
    buy_now_price = (
        parse_money(item.get("price"))
        if "FIXED_PRICE" in option_set
        else 0.0
    )

    notes_parts: list[str] = []
    if rejection:
        notes_parts.append(rejection)

    # Defensive fallback for auction-only summaries where the API returns the
    # opening/current auction price in the generic price field.
    if "AUCTION" in option_set and current_bid <= 0 and "FIXED_PRICE" not in option_set:
        current_bid = parse_money(item.get("price"))
        if current_bid > 0:
            notes_parts.append("Auction price read from eBay's generic price field")

    # Infer format only if buyingOptions was unexpectedly omitted.
    if not option_set:
        if parse_money(item.get("currentBidPrice")) > 0:
            option_set.add("AUCTION")
            current_bid = parse_money(item.get("currentBidPrice"))
        elif parse_money(item.get("price")) > 0:
            option_set.add("FIXED_PRICE")
            buy_now_price = parse_money(item.get("price"))
        options = tuple(sorted(option_set))

    if current_bid <= 0 and buy_now_price <= 0:
        return None

    if option_set == {"AUCTION", "FIXED_PRICE"}:
        listing_type = "AUCTION + BUY IT NOW"
    elif "AUCTION" in option_set:
        listing_type = "AUCTION"
    elif "FIXED_PRICE" in option_set:
        listing_type = "BUY IT NOW"
    elif "BEST_OFFER" in option_set:
        listing_type = "BEST OFFER"
    else:
        listing_type = "OTHER"

    postage = shipping_cost(item)
    if (
        settings.maximum_postage is not None
        and postage > settings.maximum_postage
    ):
        return None

    market = candidate.market_value
    target_delivered = market * settings.target_ratio

    bid_delivered = (
        current_bid + postage
        if current_bid > 0
        else None
    )
    buy_now_delivered = (
        buy_now_price + postage
        if buy_now_price > 0
        else None
    )
    bid_ratio = (
        bid_delivered / market
        if bid_delivered is not None and market
        else None
    )
    buy_now_ratio = (
        buy_now_delivered / market
        if buy_now_delivered is not None and market
        else None
    )
    maximum_bid = (
        max(0.0, target_delivered - postage)
        if current_bid > 0
        else None
    )
    bid_headroom = (
        maximum_bid - current_bid
        if maximum_bid is not None
        else None
    )
    buy_now_headroom = (
        target_delivered - buy_now_delivered
        if buy_now_delivered is not None
        else None
    )

    end_time = parse_end_time(item.get("itemEndDate"))
    minutes_remaining = max(
        0,
        int((end_time - datetime.now(timezone.utc)).total_seconds() / 60),
    )
    within_sniping_window = (
        "AUCTION" in option_set
        and minutes_remaining <= settings.ending_within_hours * 60
    )

    seller, feedback, feedback_count = seller_fields(item)
    try:
        bid_count = int(item.get("bidCount") or 0)
    except (TypeError, ValueError):
        bid_count = 0

    bid_decision = "N/A"
    bid_score = 0.0
    if bid_ratio is not None and bid_headroom is not None:
        bid_decision = decision_for(
            ratio=bid_ratio,
            match_score=match_score,
            feedback_percent=feedback,
            minimum_feedback=settings.minimum_feedback,
            target_ratio=settings.target_ratio,
            headroom=bid_headroom,
        )
        bid_score = score_listing(
            ratio=bid_ratio,
            match_score=match_score,
            feedback_percent=feedback,
            minutes_remaining=minutes_remaining,
            bid_count=bid_count,
            target_ratio=settings.target_ratio,
        )

    buy_now_decision = "N/A"
    buy_now_score = 0.0
    if buy_now_ratio is not None and buy_now_headroom is not None:
        buy_now_decision = decision_for(
            ratio=buy_now_ratio,
            match_score=match_score,
            feedback_percent=feedback,
            minimum_feedback=settings.minimum_feedback,
            target_ratio=settings.target_ratio,
            headroom=buy_now_headroom,
        )
        buy_now_score = score_listing(
            ratio=buy_now_ratio,
            match_score=match_score,
            feedback_percent=feedback,
            minutes_remaining=24 * 60,
            bid_count=0,
            target_ratio=settings.target_ratio,
        )

    decision = overall_decision(bid_decision, buy_now_decision)
    action = recommended_action(
        bid_decision,
        buy_now_decision,
        within_sniping_window,
    )
    score = max(bid_score, buy_now_score)

    # Auctions join the immediate queue when ending soon. Buy It Now listings
    # join only when they are GREEN/AMBER, because they are actionable now.
    queue_eligible = (
        within_sniping_window
        or decision == "GREEN"
        or buy_now_decision in {"GREEN", "AMBER"}
    )

    auction_url = ebay_auction_search_url(query)
    buy_url = ebay_buy_now_search_url(query)
    sold_url = ebay_sold_search_url(query)

    if feedback < settings.minimum_feedback:
        notes_parts.append("Seller feedback below configured target")
    if bid_ratio is not None and bid_ratio > settings.target_ratio:
        notes_parts.append("Current auction price exceeds configured target")
    if buy_now_ratio is not None and buy_now_ratio > settings.target_ratio:
        notes_parts.append("Buy It Now price exceeds configured target")
    if "AUCTION" in option_set and not within_sniping_window:
        notes_parts.append(
            "Auction is outside the configured sniping window of "
            f"{settings.ending_within_hours:g} hours"
        )
    if str(candidate.source or "").startswith("Manual Market Data Import H"):
        notes_parts.append(
            f"Valuation: {candidate.source} column-H manual reference"
        )
    else:
        notes_parts.append(
            "Valuation: Cardmarket 30-day average fetched on demand"
            + (
                f"; provider updated {candidate.source_date}"
                if candidate.source_date
                else ""
            )
        )

    return ListingResult(
        candidate=candidate,
        title=title,
        item_id=str(item.get("itemId", "") or ""),
        item_url=item_url(item),
        image_url=image_url(item),
        buying_options=tuple(sorted(option_set)),
        listing_type=listing_type,
        current_bid=round(current_bid, 2) if current_bid > 0 else None,
        buy_now_price=round(buy_now_price, 2) if buy_now_price > 0 else None,
        postage=round(postage, 2),
        bid_delivered=round(bid_delivered, 2) if bid_delivered is not None else None,
        buy_now_delivered=(
            round(buy_now_delivered, 2)
            if buy_now_delivered is not None
            else None
        ),
        market_value=round(market, 2),
        bid_ratio=bid_ratio,
        buy_now_ratio=buy_now_ratio,
        target_delivered=round(target_delivered, 2),
        maximum_bid=round(maximum_bid, 2) if maximum_bid is not None else None,
        bid_headroom=round(bid_headroom, 2) if bid_headroom is not None else None,
        buy_now_headroom=(
            round(buy_now_headroom, 2)
            if buy_now_headroom is not None
            else None
        ),
        bid_decision=bid_decision,
        buy_now_decision=buy_now_decision,
        recommended_action=action,
        end_time=end_time,
        minutes_remaining=minutes_remaining,
        within_sniping_window=within_sniping_window,
        queue_eligible=queue_eligible,
        bid_count=bid_count,
        seller=seller,
        feedback_percent=feedback,
        feedback_count=feedback_count,
        condition=condition_assessment.display,
        match_score=match_score,
        match_confidence=confidence_label(match_score),
        search_query=query,
        auction_search_url=auction_url,
        buy_now_search_url=buy_url,
        sold_search_url=sold_url,
        score=score,
        decision=decision,
        condition_flag=condition_assessment.flag,
        condition_details=condition_assessment.details,
        notes="; ".join(dict.fromkeys(notes_parts)),
    )


def enrich_result_condition(
    result: ListingResult,
    summary_item: dict[str, Any],
    client: EbayBrowseClient,
    logger: logging.Logger,
) -> bool:
    """Fetch detailed trading-card condition data for actionable results."""

    if result.decision not in {"GREEN", "AMBER"}:
        return False

    try:
        detail = client.get_item_details(result.item_id)
        assessment = assess_condition(summary_item, detail)
        result.condition = assessment.display
        result.condition_flag = assessment.flag
        result.condition_details = assessment.details

        if assessment.flag == "RED":
            warning = (
                "CONDITION RED — financial decision unchanged; "
                "inspect all photographs before buying or bidding"
            )
            if warning not in result.notes:
                result.notes = (
                    f"{result.notes}; {warning}"
                    if result.notes
                    else warning
                )
        return True
    except Exception as exc:
        logger.warning(
            "Could not retrieve detailed condition for %s: %s",
            result.item_id,
            exc,
        )
        return False




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
    price_resolver = None

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
        price_resolver = OnDemandPriceResolver(root, logger)
        price_resolver.set_expected_quotes(settings.maximum_attempts)
        logger.info(
            "ON-DEMAND PRICING | stored workbook prices are ignored; each "
            "selected/matched card uses Cardmarket avg30 from a live Pokemon "
            "TCG API response or a valid 24-hour checkpoint."
        )

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
            ignore_market_value=True,
        )
        logger.info(
            "Eligible identity pool: %s cards/variants; live prices will be "
            "checked against £%.2f-£%.2f on demand",
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
        seller_search_calls = 0
        item_detail_calls = 0
        seller_opportunities_added = 0

        if args.reroll_only:
            selected = select_candidates(
                eligible,
                settings,
                count=min(settings.maximum_attempts, len(eligible)),
            )
            for candidate in selected:
                quote = price_resolver.apply(candidate)
                if not quote.available:
                    continue
                if not (
                    settings.minimum_value
                    <= candidate.market_value
                    <= settings.maximum_value
                ):
                    continue
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
                        "active_search_url": ebay_auction_search_url(query),
                        "buy_now_search_url": ebay_buy_now_search_url(query),
                        "sold_search_url": ebay_sold_search_url(query),
                        "notes": "Rerolled without contacting eBay.",
                    }
                )
                if len(attempts) >= settings.number_of_cards:
                    break
            excel.write_selected_cards(attempts)
            excel.update_kpis(
                run_id,
                len(eligible),
                attempts,
                [],
                [],
                0,
                0,
                0,
                0,
                "REROLL ONLY",
            )
            excel.append_history(run_id, settings, attempts)
            excel.save()
            logger.info("Reroll complete: %s cards selected.", len(attempts))
            logger.info("ON-DEMAND PRICING | %s", price_resolver.summary())
            return 0

        client = EbayBrowseClient(
            config,
            root / "data" / "random-range-sniper.sqlite",
        )

        # eBay search can return loosely related cards. Validate each returned
        # title against the complete database before assigning the selected
        # card's market value.
        primary_identity_matcher = CandidateTitleMatcher(
            candidates
        )
        eligible_identity_set = {
            value.identity
            for value in eligible
        }

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
            quote = price_resolver.apply(candidate)
            if not quote.available:
                attempts.append(
                    {
                        "candidate": candidate,
                        "status": "PRICE UNAVAILABLE",
                        "queries_run": 0,
                        "listings_found": 0,
                        "results": [],
                        "best_result": None,
                        "target_ratio": settings.target_ratio,
                        "active_search_url": "",
                        "buy_now_search_url": "",
                        "sold_search_url": "",
                        "notes": quote.reason or quote.status,
                    }
                )
                continue
            if not (
                settings.minimum_value
                <= candidate.market_value
                <= settings.maximum_value
            ):
                attempts.append(
                    {
                        "candidate": candidate,
                        "status": "OUTSIDE LIVE PRICE RANGE",
                        "queries_run": 0,
                        "listings_found": 0,
                        "results": [],
                        "best_result": None,
                        "target_ratio": settings.target_ratio,
                        "active_search_url": "",
                        "buy_now_search_url": "",
                        "sold_search_url": "",
                        "notes": (
                            f"Fresh 30-day average £{candidate.market_value:.2f} "
                            "is outside the configured range."
                        ),
                    }
                )
                continue
            queries = build_queries(candidate, settings.search_depth)
            exact_query = queries[0]
            active_url = ebay_auction_search_url(exact_query)
            buy_now_url = ebay_buy_now_search_url(exact_query)
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
                items = client.search_listings(query, settings.listing_formats)
                api_calls += 1

                for item in items:
                    item_id = str(item.get("itemId", "") or "")
                    if not item_id or item_id in seen_items:
                        continue
                    seen_items.add(item_id)

                    detected_candidate = (
                        primary_identity_matcher.match(
                            str(
                                item.get("title", "")
                                or ""
                            ),
                            exclusions,
                        )
                    )
                    if (
                        detected_candidate is None
                        or detected_candidate.identity
                        != candidate.identity
                    ):
                        continue

                    evaluated = evaluate_item(
                        detected_candidate,
                        item,
                        query,
                        settings,
                        exclusions,
                    )
                    if evaluated:
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
                    f"{len(card_results)} matched live listing(s); "
                    f"{in_window_count} inside the sniping window."
                )
            else:
                status = (
                    "REPLACED — NO RESULTS"
                    if settings.replace_no_results
                    else "NO RESULTS"
                )
                best_result = None
                notes = "No listing passed matching and configured filters."

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
                    "buy_now_search_url": buy_now_url,
                    "sold_search_url": sold_url,
                    "notes": notes,
                }
            )

            logger.info(
                "Matched live listings: %s | In sniping window: %s",
                len(card_results),
                sum(item.within_sniping_window for item in card_results),
            )

        # Assess every matched listing before deduplication so selected-card
        # history also receives the long-term rating.
        excel.assess_results(all_results)

        # Deduplicate identical eBay items found through different cards/queries,
        # keeping the highest-scoring match.
        result_by_item: dict[str, ListingResult] = {}
        for result in all_results:
            old = result_by_item.get(result.item_id)
            if old is None or result.score > old.score:
                result_by_item[result.item_id] = result

        primary_results = sorted(
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

        seller_results: list[ListingResult] = []
        if settings.expand_green_sellers:
            matcher = CandidateTitleMatcher(candidates)
            seller_exclusions = [
                *exclusions,
                *config.get("seller_discovery_exclusions", []),
            ]

            green_anchors: list[ListingResult] = []
            seen_sellers: set[str] = set()
            for result in primary_results:
                seller_key = result.seller.casefold()
                if (
                    result.decision == "GREEN"
                    and seller_key
                    and seller_key not in seen_sellers
                ):
                    seen_sellers.add(seller_key)
                    green_anchors.append(result)

            green_anchors = green_anchors[: settings.maximum_green_sellers]

            for anchor in green_anchors:
                logger.info(
                    "GREEN seller follow-up: %s — checking other Pokémon listings",
                    anchor.seller,
                )
                try:
                    seller_items = client.search_seller_listings(
                        anchor.seller,
                        settings.listing_formats,
                        settings.seller_item_scan_limit,
                    )
                    seller_search_calls += 1
                    api_calls += 1
                except Exception as exc:
                    logger.warning(
                        "Seller follow-up failed for %s: %s",
                        anchor.seller,
                        exc,
                    )
                    continue

                discovered_for_seller: list[ListingResult] = []
                seen_seller_items: set[str] = set(result_by_item)

                for item in seller_items:
                    item_id = str(item.get("itemId", "") or "")
                    if (
                        not item_id
                        or item_id in seen_seller_items
                        or item_id == anchor.item_id
                    ):
                        continue
                    seen_seller_items.add(item_id)

                    candidate = matcher.match(
                        str(item.get("title", "") or ""),
                        seller_exclusions,
                    )
                    if (
                        candidate is None
                        or candidate.identity
                        not in eligible_identity_set
                    ):
                        continue

                    quote = price_resolver.apply(candidate)
                    if not quote.available or not (
                        settings.minimum_value
                        <= candidate.market_value
                        <= settings.maximum_value
                    ):
                        continue

                    exact_query = build_queries(candidate, "Fast")[0]
                    evaluated = evaluate_item(
                        candidate,
                        item,
                        exact_query,
                        settings,
                        exclusions,
                    )
                    if evaluated is None:
                        continue

                    # "Other opportunity" means financially GREEN/AMBER.
                    if evaluated.decision not in {"GREEN", "AMBER"}:
                        continue

                    evaluated.discovery_source = "↳ SAME SELLER"
                    evaluated.parent_item_id = anchor.item_id
                    evaluated.seller_group = anchor.seller
                    evaluated.queue_eligible = True

                    if enrich_result_condition(
                        evaluated,
                        item,
                        client,
                        logger,
                    ):
                        item_detail_calls += 1

                    discovered_for_seller.append(evaluated)

                excel.assess_results(discovered_for_seller)
                discovered_for_seller.sort(
                    key=lambda item: (
                        item.decision != "GREEN",
                        -item.long_term_score,
                        -item.score,
                        item.minutes_remaining,
                    )
                )
                discovered_for_seller = discovered_for_seller[
                    : settings.maximum_seller_opportunities
                ]

                seller_results.extend(discovered_for_seller)
                seller_opportunities_added += len(discovered_for_seller)

                logger.info(
                    "Seller follow-up %s: %s additional opportunity/opportunities",
                    anchor.seller,
                    len(discovered_for_seller),
                )

        all_results = [
            *primary_results,
            *seller_results,
        ][: int(config["maximum_result_rows"])]

        primary_queue = [
            result for result in primary_results
            if result.queue_eligible
        ]
        seller_queue = [
            result for result in seller_results
            if result.queue_eligible
        ]
        random_queue = group_queue_results(
            primary_queue,
            seller_queue,
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
            seller_search_calls,
            item_detail_calls,
            seller_opportunities_added,
            "LIVE EBAY SCAN",
        )

        copied = 0
        if settings.copy_green_to_main_queue:
            copied = excel.copy_green_to_snipe_queue(random_queue)

        long_term_update = excel.update_long_term_records(
            "RANDOM SNIPER",
            all_results,
            eligible,
        )
        logger.info(
            "Long-term records | price snapshots=%s | portfolio rows refreshed=%s",
            long_term_update.get("snapshots", 0),
            long_term_update.get("portfolio_rows", 0),
        )

        excel.save()

        logger.info("Random Range Sniper completed successfully.")
        logger.info("Cards attempted: %s", len(attempts))
        logger.info("Cards with matched listings: %s", successful_cards)
        logger.info("Total matched live listings: %s", len(all_results))
        logger.info("Random Snipe Queue rows: %s", len(random_queue))
        logger.info(
            "Queue GREEN: %s | AMBER: %s | RED: %s",
            sum(item.decision == "GREEN" for item in random_queue),
            sum(item.decision == "AMBER" for item in random_queue),
            sum(item.decision == "RED" for item in random_queue),
        )
        logger.info("Total eBay API calls: %s", api_calls + item_detail_calls)
        logger.info("Seller follow-up searches: %s", seller_search_calls)
        logger.info("Detailed condition calls: %s", item_detail_calls)
        logger.info(
            "Seller opportunities added: %s",
            seller_opportunities_added,
        )
        logger.info("ON-DEMAND PRICING | %s", price_resolver.summary())
        logger.info("GREEN rows copied to Snipe Queue: %s", copied)
        print()
        print("RANDOM RANGE SNIPER SUCCESSFUL")
        print(f"Run ID: {run_id}")
        print(f"Cards attempted: {len(attempts)}")
        print(f"Cards with results: {successful_cards}")
        print(f"Matched live listings: {len(all_results)}")
        print(f"Random Snipe Queue rows: {len(random_queue)}")
        print(f"Seller opportunities added: {seller_opportunities_added}")
        print(
            "Strong long-term opportunities (score 80+): "
            f"{sum(item.long_term_score >= 80 for item in all_results)}"
        )
        print(
            "Queue GREEN opportunities: "
            f"{sum(item.decision == 'GREEN' for item in random_queue)}"
        )
        print(f"On-demand pricing: {price_resolver.summary()}")
        return 0

    finally:
        if price_resolver is not None:
            price_resolver.close()
        if client is not None:
            client.close()
        if excel is not None:
            excel.close(save=True)


if __name__ == "__main__":
    raise SystemExit(main())
