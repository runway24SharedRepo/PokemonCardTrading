from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .core import normalize_text


@dataclass(frozen=True)
class ConditionAssessment:
    display: str
    flag: str
    details: str


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
    "ink",
    "writing",
    "peeling",
    "altered",
    "trimmed",
    "stain",
    "dent",
    "ripped",
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
    "surface wear",
    "played",
    "wear",
)

GREEN_TERMS = (
    "near mint or better",
    "near mint",
    "mint",
    "pack fresh",
    "fresh pack",
    "new",
)


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


def _descriptor_texts(item: dict[str, Any]) -> list[str]:
    output: list[str] = []

    for descriptor in item.get("conditionDescriptors") or []:
        name = str(descriptor.get("name", "") or "").strip()
        values = descriptor.get("values") or []

        for raw in values:
            if isinstance(raw, dict):
                content = str(raw.get("content", "") or "").strip()
                extra = raw.get("additionalInfo") or []
            else:
                content = str(raw or "").strip()
                extra = []

            content = CARD_CONDITION_VALUES.get(
                content,
                content,
            )
            if content:
                output.append(content)

            for value in extra:
                text = str(value or "").strip()
                if text:
                    output.append(text)

        if (
            name
            and name not in {"40001", "27501", "27502", "27503"}
        ):
            output.append(name)

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

    display = " | ".join(
        _unique([base, *descriptors])
    ) or "Condition not supplied"

    evidence = normalize_text(
        " | ".join(_unique([display, description]))
    )

    if any(term in evidence for term in RED_TERMS):
        flag = "RED"
    elif any(term in evidence for term in AMBER_TERMS):
        flag = "AMBER"
    elif any(term in evidence for term in GREEN_TERMS):
        flag = "GREEN"
    elif "ungraded" in evidence:
        flag = "AMBER"
    else:
        flag = "UNKNOWN"

    details = description
    if not details and descriptors:
        details = (
            "Structured eBay card condition: "
            + "; ".join(descriptors)
        )
    if not details:
        details = (
            "No detailed condition description supplied; "
            "inspect all photographs."
        )

    return ConditionAssessment(
        display=display,
        flag=flag,
        details=details,
    )
