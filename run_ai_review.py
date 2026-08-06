from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from ai_review_cache import AIReviewCache
from ai_review_ebay import AIReviewEbayClient, compact_item_details
from ai_review_excel import AIExcelAdapter
from ai_review_logic import (
    ReviewPolicy,
    build_candidate_shortlist,
    derive_action,
    review_priority,
    should_review,
)
from ai_review_openai import OpenAIListingReviewer
from ai_review_models import ListingRow


def configure_logging(root: Path) -> logging.Logger:
    logger = logging.getLogger("ai-review")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(root / "ai-review.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Text-only OpenAI review of Pokémon eBay listings in the workbook."
    )
    parser.add_argument("--mode", choices=["smart", "selected", "urgent"], default="smart")
    return parser.parse_args()


def text(value: Any) -> str:
    return str(value or "").strip()


def yes(value: Any) -> bool:
    return text(value).casefold() in {"yes", "true", "1", "on"}


def integer(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def decimal(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_policy(settings: dict[str, Any]) -> ReviewPolicy:
    decisions = tuple(
        value.strip().upper()
        for value in text(settings.get("Review Decisions", "GREEN,AMBER")).split(",")
        if value.strip()
    )
    return ReviewPolicy(
        minimum_market_value_gbp=decimal(
            settings.get("Minimum Market Value GBP", 20), 20
        ),
        review_decisions=decisions or ("GREEN", "AMBER"),
        review_low_confidence=yes(settings.get("Review Low Confidence", "YES")),
        review_risk_terms=yes(settings.get("Review Risk Terms", "YES")),
        review_edition_terms=yes(settings.get("Review Edition Terms", "YES")),
        include_archives=yes(settings.get("Include Archives", "NO")),
        urgent_max_minutes=integer(settings.get("Urgent Maximum Minutes", 180), 180),
    )


def details_fallback(row: ListingRow) -> dict[str, Any]:
    return {
        "title": row.title,
        "short_description": "",
        "condition": row.condition,
        "condition_description": row.condition_details,
        "item_specifics": [],
        "buying_options": [],
        "seller": {
            "username": row.seller,
            "feedback_percentage": "",
            "feedback_score": "",
        },
    }


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    logger = configure_logging(root)
    load_dotenv(root / ".env", override=True, encoding="utf-8-sig")

    workbook_path = Path(
        os.getenv("WORKBOOK_PATH", "Pokemon-Auction-Scanner-Dashboard.xlsx")
    )
    if not workbook_path.is_absolute():
        workbook_path = root / workbook_path
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY is missing. Run configureGPT.bat.")

    excel: AIExcelAdapter | None = None
    cache: AIReviewCache | None = None
    ebay: AIReviewEbayClient | None = None
    reviews = cache_hits = skipped = errors = 0

    try:
        logger.info("AI REVIEW START | mode=%s", args.mode)
        excel = AIExcelAdapter(workbook_path)
        updated = excel.ensure_all_structure()
        logger.info("AI structure checked on %s worksheet(s).", len(updated))
        settings = excel.read_settings()
        if not yes(settings.get("AI Enabled", "YES")):
            logger.info("AI Enabled is NO. No reviews were performed.")
            excel.save()
            return 0

        model = text(settings.get("Model", "gpt-5.6-luna")) or "gpt-5.6-luna"
        reasoning_effort = text(settings.get("Reasoning Effort", "low")) or "low"
        max_reviews = max(1, integer(settings.get("Maximum Reviews Per Run", 20), 20))
        monthly_budget = max(0.0, decimal(settings.get("Monthly Budget USD", 5), 5))
        reserve_per_review = max(
            0.0, decimal(settings.get("Reserve Per Review USD", 0.05), 0.05)
        )
        auto_accept = max(
            0, min(100, integer(settings.get("Auto Accept Confidence", 95), 95))
        )
        maximum_output_tokens = max(
            200, integer(settings.get("Maximum Output Tokens", 650), 650)
        )
        fetch_ebay = yes(settings.get("Fetch eBay Text Details", "YES"))
        policy = build_policy(settings)

        cache = AIReviewCache(root / "data" / "ai-review-cache.sqlite")
        current_spend = cache.current_month_spend()
        logger.info(
            "Model=%s | month spend=$%.4f | budget=$%.2f",
            model,
            current_spend,
            monthly_budget,
        )
        all_candidates = excel.read_market_candidates()
        logger.info("Candidate variants loaded: %s", len(all_candidates))
        rows = excel.collect_rows(
            include_archives=(policy.include_archives or args.mode == "selected")
        )
        for row in rows:
            excel.clear_stale_ai(row)
        eligible = [row for row in rows if should_review(row, args.mode, policy)]
        eligible.sort(key=review_priority)
        logger.info("Workbook rows=%s | eligible=%s", len(rows), len(eligible))

        reviewer = OpenAIListingReviewer(
            model=model,
            reasoning_effort=reasoning_effort,
            maximum_output_tokens=maximum_output_tokens,
        )
        if fetch_ebay:
            try:
                config = json.loads(
                    (root / "random-sniper-config.json").read_text(encoding="utf-8")
                )
                ebay = AIReviewEbayClient(config, cache)
            except Exception as exc:
                logger.warning("eBay text details disabled for this run: %s", exc)

        for index, row in enumerate(eligible, start=1):
            shortlist = build_candidate_shortlist(row, all_candidates, maximum=5)
            details = details_fallback(row)
            if ebay is not None:
                try:
                    details = compact_item_details(ebay.get_item_details(row.item_id))
                except Exception as exc:
                    logger.warning("eBay detail fetch failed for %s: %s", row.item_id, exc)

            # Build exactly the same fingerprint that reviewer.review will use.
            _, fingerprint = reviewer.build_payload(row, shortlist, details)
            cached = cache.get_review(fingerprint)
            if cached is not None:
                execution = cached
                cache_hits += 1
            else:
                if reviews >= max_reviews:
                    skipped += len(eligible) - index + 1
                    logger.info("Maximum new API reviews reached.")
                    break
                current_spend = cache.current_month_spend()
                if (
                    monthly_budget > 0
                    and current_spend + reserve_per_review > monthly_budget
                ):
                    excel.write_status(
                        row,
                        "BUDGET LIMIT",
                        note="Monthly AI budget reserve reached.",
                    )
                    skipped += len(eligible) - index + 1
                    logger.info("Monthly budget reserve reached.")
                    break
                logger.info(
                    "AI review %s/%s | %s | %s",
                    reviews + 1,
                    min(len(eligible), max_reviews),
                    row.sheet_name,
                    row.title[:90],
                )
                try:
                    execution = reviewer.review(row, shortlist, details)
                    cache.put_review(execution)
                    reviews += 1
                except Exception as exc:
                    errors += 1
                    excel.write_status(
                        row,
                        "API ERROR",
                        note=f"{type(exc).__name__}: {str(exc)[:500]}",
                    )
                    logger.exception(
                        "AI review failed for %s row %s.",
                        row.sheet_name,
                        row.row_number,
                    )
                    continue

            status, action = derive_action(
                execution.review, row.current_candidate_key, auto_accept
            )
            excel.write_review(row, execution, status, action)
            excel.append_log(row, execution, status, action)
            logger.info(
                "%s | %s | confidence=%s%% | risk=%s | cache=%s",
                status,
                action,
                execution.review.confidence_percent,
                execution.review.listing_risk,
                execution.cached,
            )

        current_spend = cache.current_month_spend()
        excel.update_usage_summary(
            month_spend=current_spend,
            reviews=reviews,
            cache_hits=cache_hits,
            skipped=skipped,
            errors=errors,
            mode=args.mode,
        )
        excel.save()
        print()
        print("TEXT-ONLY AI REVIEW COMPLETE")
        print(f"Mode: {args.mode}")
        print(f"New API reviews: {reviews}")
        print(f"Cache hits: {cache_hits}")
        print(f"Rows skipped: {skipped}")
        print(f"API errors: {errors}")
        print(f"Current month estimated spend: ${current_spend:.4f}")
        print("Images sent: 0")
        return 0
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        return 130
    except Exception as exc:
        logger.exception("AI REVIEW FAILED: %s", exc)
        return 1
    finally:
        if ebay is not None:
            ebay.close()
        if cache is not None:
            cache.close()
        if excel is not None:
            excel.close(save=True)


if __name__ == "__main__":
    raise SystemExit(main())
