from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalise_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    ).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def is_first_edition_variant(value: Any) -> bool:
    text = normalise_text(value)
    return (
        "1st edition" in text
        or "first edition" in text
    )


def is_shadowless_variant(value: Any) -> bool:
    return "shadowless" in normalise_text(value)


def title_says_first_edition(value: Any) -> bool:
    text = normalise_text(value)
    return (
        "1st edition" in text
        or "first edition" in text
        or "1st ed" in text
    )


def title_says_unlimited(value: Any) -> bool:
    text = normalise_text(value)
    return (
        "unlimited" in text
        or "unlimited edition" in text
    )


def title_says_shadowless(value: Any) -> bool:
    return "shadowless" in normalise_text(value)


def edition_conflict(
    candidate_variant: Any,
    listing_title: Any,
) -> str:
    """Hard edition gate.

    First Edition is never inferred. An unmarked vintage title is treated as
    standard/Unlimited unless the title explicitly states another edition.
    """

    candidate_first = is_first_edition_variant(candidate_variant)
    candidate_shadowless = is_shadowless_variant(candidate_variant)
    title_first = title_says_first_edition(listing_title)
    title_unlimited = title_says_unlimited(listing_title)
    title_shadowless = title_says_shadowless(listing_title)

    if title_first and not candidate_first:
        return "Edition conflict: listing explicitly says 1st Edition"

    if candidate_first and not title_first:
        if title_unlimited:
            return "Edition conflict: listing explicitly says Unlimited"
        return (
            "Edition conflict: First Edition pricing requires explicit "
            "1st Edition evidence in the listing title"
        )

    if title_shadowless and not candidate_shadowless:
        return "Edition conflict: listing explicitly says Shadowless"

    if candidate_shadowless and not title_shadowless:
        return (
            "Edition conflict: Shadowless pricing requires explicit "
            "Shadowless evidence"
        )

    return ""


def edition_variant_score(
    candidate_variant: Any,
    listing_title: Any,
) -> float | None:
    """Edition-specific score, or None for ordinary variant scoring."""

    variant = normalise_text(candidate_variant)
    title = normalise_text(listing_title)

    if is_first_edition_variant(variant):
        if not title_says_first_edition(title):
            return 0.0

        candidate_holo = "holo" in variant
        title_holo = "holo" in title or "foil" in title
        if candidate_holo:
            return 1.0 if title_holo else 0.45
        return 0.20 if title_holo else 1.0

    if is_shadowless_variant(variant):
        return 1.0 if title_says_shadowless(title) else 0.0

    if variant in {
        "normal",
        "unlimited",
        "unlimited normal",
        "standard",
    }:
        if title_says_unlimited(title):
            return 1.0
        return None

    return None


def is_positive_number(value: Any) -> bool:
    try:
        return float(value or 0) > 0
    except (TypeError, ValueError):
        return False


def safe_reference_image_url(
    image_url: Any,
    first_edition_normal_price: Any,
    first_edition_holo_price: Any,
) -> str:
    """Card-level API images do not prove the selected vintage edition."""

    if (
        is_positive_number(first_edition_normal_price)
        or is_positive_number(first_edition_holo_price)
    ):
        return ""
    return str(image_url or "").strip()


def preferred_result_image(
    listing_image_url: Any,
    reference_image_url: Any,
) -> str:
    return (
        str(listing_image_url or "").strip()
        or str(reference_image_url or "").strip()
    )
