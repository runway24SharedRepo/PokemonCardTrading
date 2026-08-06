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
                if (
                    len(token) >= 2
                    and token not in {
                        "ex",
                        "gx",
                        "vmax",
                        "vstar",
                        "break",
                        "prime",
                    }
                ):
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
            for candidate in self._token_index.get(
                token,
                [],
            ):
                candidate_pool[
                    candidate.identity
                ] = candidate

        scored: list[
            tuple[float, float, Candidate]
        ] = []

        for candidate in candidate_pool.values():
            score, _ = listing_match_score(
                candidate,
                title,
                exclusions,
            )
            if score < 0.72:
                continue

            set_tokens = meaningful_tokens(
                candidate.set_name
            )
            set_score = (
                sum(
                    token in title_tokens
                    for token in set_tokens
                )
                / len(set_tokens)
                if set_tokens
                else 0.0
            )
            scored.append(
                (
                    score,
                    set_score,
                    candidate,
                )
            )

        if not scored:
            return None

        scored.sort(
            key=lambda value: (
                value[0],
                value[1],
                value[2].market_value,
            ),
            reverse=True,
        )
        best_score, best_set_score, best = (
            scored[0]
        )

        if len(scored) > 1:
            (
                second_score,
                second_set_score,
                second,
            ) = scored[1]

            same_exact_identity = (
                best.identity == second.identity
            )
            clear_set_advantage = (
                best_set_score >= 0.75
                and best_set_score
                - second_set_score >= 0.35
            )
            clear_score_advantage = (
                best_score - second_score >= 0.055
            )

            if (
                not same_exact_identity
                and not clear_set_advantage
                and not clear_score_advantage
            ):
                # It is safer to discard a listing than assign the market
                # value of a different set or variant.
                return None

        return best


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
