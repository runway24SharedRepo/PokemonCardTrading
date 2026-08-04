from __future__ import annotations
from difflib import SequenceMatcher
from .models import CardMatch, PriceRecord
from .title_parser import normalise, parse_title

class PriceCatalog:
    def __init__(self, records: list[PriceRecord]) -> None:
        self.records = [r for r in records if r.market_value > 0]

    def match(self, title: str) -> CardMatch:
        parsed = parse_title(title)
        best: tuple[float, PriceRecord, str] | None = None
        for record in self.records:
            name = normalise(record.card_name)
            if not name or name not in parsed.normalised:
                continue
            score = 0.55
            reasons = ["name"]
            card_no = normalise(record.card_number).replace(" ", "")
            if card_no and any(card_no in n.lower().replace(" ", "") or n.lower().replace(" ", "") in card_no
                               for n in parsed.card_numbers):
                score += 0.28
                reasons.append("card number")
            set_name = normalise(record.set_name)
            if set_name and set_name in parsed.normalised:
                score += 0.12
                reasons.append("set")
            variant = normalise(record.variant)
            if variant and variant in parsed.normalised:
                score += 0.08
                reasons.append("variant")
            # Penalise an explicit mismatch for first edition / stamped.
            rec_first = "first edition" in variant or "1st edition" in variant
            title_first = "first edition" in parsed.variants
            if rec_first != title_first and (rec_first or title_first):
                score -= 0.22
                reasons.append("edition uncertainty")
            score = max(0.0, min(1.0, score))
            if best is None or score > best[0]:
                best = (score, record, ", ".join(reasons))
        if best:
            score, rec, reason = best
            label = f"{rec.card_name} {rec.card_number}".strip()
            return CardMatch(label, score, rec.market_value, reason, rec)

        # Fuzzy fallback only for clear long names.
        for record in self.records:
            name = normalise(record.card_name)
            if len(name) < 6:
                continue
            words = parsed.normalised.split()
            windows = [" ".join(words[i:i+len(name.split())]) for i in range(len(words))]
            similarity = max((SequenceMatcher(None, name, w).ratio() for w in windows), default=0)
            if similarity >= 0.88:
                score = similarity * 0.62
                if best is None or score > best[0]:
                    best = (score, record, "fuzzy name")
        if best:
            score, rec, reason = best
            return CardMatch(f"{rec.card_name} {rec.card_number}".strip(), score, rec.market_value, reason, rec)
        return CardMatch("UNMATCHED", 0.0, 0.0, "no pricing record matched", None)
