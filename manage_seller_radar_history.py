from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from seller_radar_history import SellerRadarHistory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect or reset Seller Radar scan history."
    )
    parser.add_argument(
        "--seller",
        help=(
            "Reset or inspect one seller directly. Retained for "
            "backward compatibility."
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
    )
    parser.add_argument(
        "--selection",
        help=(
            "Number selection such as 3;4, 1,3, 2-4 or A. "
            "Primarily useful for scripted operation."
        ),
    )
    parser.add_argument(
        "--interactive-reset",
        action="store_true",
        help="Show the numbered tracked-seller selector.",
    )
    return parser.parse_args()


def friendly_time(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "not recorded"
    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
        return parsed.astimezone().strftime(
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        return text


def plural(value: int, singular: str, plural_word: str | None = None) -> str:
    word = singular if value == 1 else (plural_word or singular + "s")
    return f"{value} {word}"


def print_seller_list(
    tracked: list[dict[str, Any]],
) -> None:
    print()
    print("Currently tracked Seller Radar histories:")
    print()

    number_width = len(str(len(tracked)))
    for number, entry in enumerate(tracked, start=1):
        seller = entry["seller"]
        scanned = int(entry["scanned_count"])
        runs = int(entry["run_count"])
        updated = friendly_time(entry["updated_at"])

        print(
            f"  {number:>{number_width}}) {seller}"
            f"  [{plural(scanned, 'listing')}, "
            f"{plural(runs, 'batch', 'batches')}, "
            f"updated {updated}]"
        )

    print()
    print("Selection examples:")
    print("  3;4   remove sellers 3 and 4")
    print("  1,3   remove sellers 1 and 3")
    print("  2-4   remove sellers 2 through 4")
    print("  A     remove every tracked seller")
    print("  Q     cancel")


def parse_selection(
    value: str,
    seller_count: int,
) -> list[int]:
    """Parse one-based seller numbers, ranges, separators or ALL."""

    text = str(value or "").strip().upper()
    if not text:
        raise ValueError("No seller number was entered.")
    if text in {"Q", "QUIT", "CANCEL"}:
        return []
    if text in {"A", "ALL", "*"}:
        return list(range(1, seller_count + 1))

    # Accept semicolons, commas and whitespace.
    tokens = [
        token
        for token in re.split(r"[;,\s]+", text)
        if token
    ]
    selected: list[int] = []
    seen: set[int] = set()

    for token in tokens:
        range_match = re.fullmatch(
            r"(\d+)\s*-\s*(\d+)",
            token,
        )
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start > end:
                start, end = end, start
            numbers = range(start, end + 1)
        elif token.isdigit():
            numbers = [int(token)]
        else:
            raise ValueError(
                f"Unrecognised selection '{token}'. "
                "Use numbers such as 3;4, a range such as 2-4, "
                "A for all, or Q to cancel."
            )

        for number in numbers:
            if number < 1 or number > seller_count:
                raise ValueError(
                    f"Seller number {number} is outside the valid "
                    f"range 1-{seller_count}."
                )
            if number not in seen:
                seen.add(number)
                selected.append(number)

    return selected


def ask_for_selection(
    tracked: list[dict[str, Any]],
) -> list[int]:
    while True:
        print()
        raw = input(
            "Which seller history should be removed? "
            "(example 3;4): "
        )
        try:
            return parse_selection(
                raw,
                len(tracked),
            )
        except ValueError as exc:
            print(f"ERROR: {exc}")


def confirm_selection(
    entries: list[dict[str, Any]],
) -> bool:
    print()
    print("Selected seller histories:")
    total_items = 0

    for entry in entries:
        scanned = int(entry["scanned_count"])
        total_items += scanned
        print(
            f"  - {entry['seller']} "
            f"({plural(scanned, 'listing')}, "
            f"{plural(int(entry['run_count']), 'batch', 'batches')})"
        )

    print()
    print(
        f"Total: {plural(len(entries), 'seller')} and "
        f"{plural(total_items, 'recorded listing')}."
    )
    print(
        "This resets Seller Radar progress only. "
        "The Excel seller worksheets are not deleted."
    )
    print(
        "The next Seller Radar run for these sellers will begin "
        "again from their first currently active listings."
    )
    print()

    confirmation = input(
        "Type RESET SELECTED to continue: "
    ).strip()
    return confirmation == "RESET SELECTED"


def interactive_reset(
    history: SellerRadarHistory,
    supplied_selection: str | None,
    assume_yes: bool,
) -> int:
    tracked = history.tracked_sellers()
    if not tracked:
        print()
        print("There are no sellers currently tracked by Seller Radar.")
        print(
            "Run sellerRadar.bat successfully at least once to "
            "create seller history."
        )
        return 0

    print_seller_list(tracked)

    try:
        selected_numbers = (
            parse_selection(
                supplied_selection,
                len(tracked),
            )
            if supplied_selection is not None
            else ask_for_selection(tracked)
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    if not selected_numbers:
        print()
        print("Cancelled. Seller history was not changed.")
        return 0

    selected_entries = [
        tracked[number - 1]
        for number in selected_numbers
    ]

    if not assume_yes and not confirm_selection(
        selected_entries
    ):
        print()
        print("Cancelled. Seller history was not changed.")
        return 0

    removed, backup_path = history.reset_sellers(
        [entry["seller"] for entry in selected_entries],
        backup=True,
    )
    history.save()

    print()
    print("SELLER RADAR HISTORY RESET COMPLETE")
    total_removed = 0
    for entry in selected_entries:
        seller = entry["seller"]
        removed_count = int(removed.get(seller, 0))
        total_removed += removed_count
        print(
            f"  {seller}: removed "
            f"{plural(removed_count, 'recorded listing')}"
        )

    print()
    print(
        f"Removed {plural(len(removed), 'seller history', 'seller histories')} "
        f"containing {plural(total_removed, 'recorded listing')}."
    )
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    print("Seller worksheets were preserved.")
    return 0


def legacy_single_seller(
    history: SellerRadarHistory,
    seller: str,
    reset: bool,
    assume_yes: bool,
) -> int:
    seller = str(seller or "").strip()
    count = history.scanned_count(seller)
    runs = history.completed_run_count(seller)

    print(f"Seller: {seller}")
    print(f"Recorded scanned listing IDs: {count}")
    print(f"Completed recorded batches: {runs}")

    if not reset:
        return 0
    if count == 0:
        print("There is no Seller Radar history to reset.")
        return 0

    if not assume_yes:
        print()
        print(
            "Resetting makes the next Seller Radar run begin again "
            "from the seller's first currently active listings."
        )
        confirmation = input(
            "Type RESET SELLER to continue: "
        ).strip()
        if confirmation != "RESET SELLER":
            print("Cancelled. History was not changed.")
            return 0

    removed, backup_path = history.reset_sellers(
        [seller],
        backup=True,
    )
    history.save()

    removed_count = sum(removed.values())
    print(
        f"Reset complete. Removed "
        f"{plural(removed_count, 'recorded listing')}."
    )
    if backup_path is not None:
        print(f"Backup: {backup_path}")
    return 0


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    history = SellerRadarHistory(
        root / "data" / "seller-radar-scan-history.json"
    )

    if args.seller:
        return legacy_single_seller(
            history,
            args.seller,
            args.reset,
            args.yes,
        )

    # Numbered selection is now the default when launched without --seller.
    return interactive_reset(
        history,
        args.selection,
        args.yes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
