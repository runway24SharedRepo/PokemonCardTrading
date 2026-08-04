from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass

CARD_NUMBER_PATTERNS = [
    re.compile(r"\b([A-Z]{0,5}\d{1,4})\s*/\s*([A-Z]{0,5}\d{1,4})\b", re.I),
    re.compile(r"\b(SVP|SWSH|SM|XY|BW)\s*[- ]?(\d{1,4})\b", re.I),
    re.compile(r"\b(TG|GG|RC)\s*(\d{1,3})(?:\s*/\s*(?:TG|GG|RC)?\d{1,3})?\b", re.I),
]
VARIANT_TERMS = {
    "first edition": ("1st edition", "first edition", "edition 1"),
    "reverse holo": ("reverse holo", "reverse foil"),
    "holo": ("holofoil", "holo foil", "holo"),
    "pokemon center stamped": ("pokemon center stamped", "pokemon centre stamped"),
    "stamped": ("stamped promo", "stamped"),
    "shadowless": ("shadowless",),
}
CONDITION_TERMS = {
    "damaged": ("damaged","crease","creased","bent","water damage"),
    "played": ("heavily played","moderately played","played","hp","mp"),
    "lightly played": ("lightly played","lp"),
    "near mint": ("near mint","nm","mint","pack fresh"),
}

def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("pokémon", "pokemon")
    text = re.sub(r"[^a-z0-9/+\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

@dataclass(frozen=True)
class ParsedTitle:
    normalised: str
    card_numbers: tuple[str, ...]
    variants: tuple[str, ...]
    stated_condition: str

def parse_title(title: str) -> ParsedTitle:
    norm = normalise(title)
    nums: list[str] = []
    for pattern in CARD_NUMBER_PATTERNS:
        for match in pattern.finditer(norm):
            nums.append("".join(g for g in match.groups() if g).upper())
            nums.append(match.group(0).upper().replace(" ", ""))
    variants = [name for name, terms in VARIANT_TERMS.items() if any(t in norm for t in terms)]
    stated = "unknown"
    for condition, terms in CONDITION_TERMS.items():
        if any(re.search(rf"\b{re.escape(term)}\b", norm) for term in terms):
            stated = condition
            break
    return ParsedTitle(norm, tuple(dict.fromkeys(nums)), tuple(variants), stated)
