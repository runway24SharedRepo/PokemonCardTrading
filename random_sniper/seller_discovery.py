from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .core import (
    Candidate,
    ListingResult,
    card_number_match,
    listing_match_score,
    meaningful_tokens,
    normalize_text,
)


class CandidateTitleMatcher:
    """Find an exact database candidate for an unknown seller listing title."""

    def __init__(self, candidates: Iterable[Candidate]) -> None:
        self._token_index: dict[str, list[Candidate]] = defaultdict(list)

        for candidate in candidates:
            tokens = meaningful_tokens(candidate.name)
            for token in set(tokens):
                if len(token) >= 3:
                    self._token_index[token].append(candidate)

    def match(
        self,
        title: str,
        exclusions: Iterable[str],
    ) -> Candidate | None:
        normalized = normalize_text(title)
        title_tokens = set(normalized.split())

        candidate_pool: dict[str, Candidate] = {}
        for token in title_tokens:
            for candidate in self._token_index.get(token, []):
                candidate_pool[candidate.identity] = candidate

        best_candidate: Candidate | None = None
        best_score = 0.0

        for candidate in candidate_pool.values():
            # Seller discovery must be stricter than an ordinary known-card
            # search. Exact card-number evidence is required.
            if card_number_match(title, candidate.number) < 0.75:
                continue

            score, _ = listing_match_score(candidate, title, exclusions)
            if score > best_score:
                best_score = score
                best_candidate = candidate

        return best_candidate if best_score >= 0.72 else None


def group_queue_results(
    primary_results: list[ListingResult],
    seller_results: list[ListingResult],
) -> list[ListingResult]:
    """Place seller discoveries immediately below the first GREEN anchor."""

    by_seller: dict[str, list[ListingResult]] = defaultdict(list)
    for result in seller_results:
        by_seller[result.seller.casefold()].append(result)

    for values in by_seller.values():
        values.sort(
            key=lambda item: (
                item.decision != "GREEN",
                item.decision == "RED",
                -item.score,
                item.minutes_remaining,
            )
        )

    output: list[ListingResult] = []
    inserted_sellers: set[str] = set()

    for result in primary_results:
        output.append(result)
        seller_key = result.seller.casefold()

        if (
            result.decision == "GREEN"
            and seller_key
            and seller_key not in inserted_sellers
        ):
            output.extend(by_seller.get(seller_key, []))
            inserted_sellers.add(seller_key)

    # Defensive fallback for any discovery whose anchor was removed during
    # deduplication.
    for seller_key, values in by_seller.items():
        if seller_key not in inserted_sellers:
            output.extend(values)

    return output
