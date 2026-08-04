from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .core import normalize_text


@dataclass(frozen=True)
class ConditionAssessment:
    display: str
    flag: str
    details: str


# eBay UK trading-card condition descriptor values. The Browse getItem call
# normally returns human-readable content, but numeric IDs are supported too.
CARD_CONDITION_VALUES = {
    "400010": "Near Mint or Better",
    "400011": "Excellent",
    "400012": "Very Good",
    "400013": "Poor",
    "400015": "Lightly Played (Excellent)",
    "400016": "Moderately Played (Very Good)",
    "400017": "Heavily Played (Poor)",
}

RED_TERMS = (
    "poor",
    "heavily played",
    "damaged",
    "damage",
    "crease",
    "creased",
    "bent",
    "torn",
    "tear",
    "water damage",
    "water damaged",
    "ink",
    "writing",
    "peeling",
    "altered",
    "trimmed",
    "stain",
    "stained",
    "dent",
    "dented",
    "ripped",
    "hole",
    "missing piece",
)

AMBER_TERMS = (
    "moderately played",
    "very good",
    "lightly played",
    "excellent",
    "minor corner",
    "edge wear",
    "corner wear",
    "whitening",
    "scratch",
    "scratches",
    "surface wear",
    "played",
    "wear",
)

GREEN_TERMS = (
    "near mint or better",
    "near mint",
    "mint",
    "comparable to a fresh pack",
    "fresh pack",
    "pack fresh",
    "new",
)


def _descriptor_texts(item: dict[str, Any]) -> list[str]:
    output: list[str] = []

    for descriptor in item.get("conditionDescriptors") or []:
        name = str(descriptor.get("name", "") or "").strip()
        for raw_value in descriptor.get("values") or []:
            if isinstance(raw_value, dict):
                content = str(raw_value.get("content", "") or "").strip()
                additional = raw_value.get("additionalInfo") or []
            else:
                content = str(raw_value or "").strip()
                additional = []

            content = CARD_CONDITION_VALUES.get(content, content)
            if content:
                output.append(content)

            for value in additional:
                text = str(value or "").strip()
                if text:
                    output.append(text)

        # Some API representations can expose numeric/string values directly.
        direct_values = descriptor.get("value") or []
        if isinstance(direct_values, (str, int)):
            direct_values = [direct_values]
        for raw_value in direct_values:
            text = CARD_CONDITION_VALUES.get(
                str(raw_value).strip(),
                str(raw_value).strip(),
            )
            if text:
                output.append(text)

        if name and name not in {"40001", "27501", "27502", "27503"}:
            output.append(name)

    return output


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
    return output


def assess_condition(
    summary_item: dict[str, Any],
    detail_item: dict[str, Any] | None = None,
) -> ConditionAssessment:
    detail = detail_item or {}

    base = str(
        detail.get("condition")
        or summary_item.get("condition")
        or "Condition not supplied"
    ).strip()
    description = str(
        detail.get("conditionDescription")
        or summary_item.get("conditionDescription")
        or ""
    ).strip()

    descriptors = _descriptor_texts(detail)
    if not descriptors:
        descriptors = _descriptor_texts(summary_item)

    display_parts = _unique([base, *descriptors])
    display = " | ".join(display_parts) or "Condition not supplied"

    evidence_parts = _unique([display, description])
    evidence = " | ".join(evidence_parts)
    normalized = normalize_text(evidence)

    if any(term in normalized for term in RED_TERMS):
        flag = "RED"
    elif any(term in normalized for term in AMBER_TERMS):
        flag = "AMBER"
    elif any(term in normalized for term in GREEN_TERMS):
        flag = "GREEN"
    elif "ungraded" in normalized:
        # Ungraded without a specific card-condition descriptor needs a visual
        # inspection, but is not automatically rejected.
        flag = "AMBER"
    else:
        flag = "UNKNOWN"

    details = description
    if not details and descriptors:
        details = "Structured eBay card condition: " + "; ".join(descriptors)
    if not details:
        details = "No detailed condition description supplied by the seller."

    return ConditionAssessment(
        display=display,
        flag=flag,
        details=details,
    )
