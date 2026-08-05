from __future__ import annotations

import argparse
from pathlib import Path

from seller_radar_history import SellerRadarHistory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect or reset Seller Radar scan history."
    )
    parser.add_argument("--seller", required=True)
    parser.add_argument(
        "--reset",
        action="store_true",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    history = SellerRadarHistory(
        root / "data" / "seller-radar-scan-history.json"
    )

    seller = str(args.seller or "").strip()
    count = history.scanned_count(seller)
    runs = history.completed_run_count(seller)

    print(f"Seller: {seller}")
    print(f"Recorded scanned listing IDs: {count}")
    print(f"Completed recorded batches: {runs}")

    if not args.reset:
        return 0

    if count == 0:
        print("There is no Seller Radar history to reset.")
        return 0

    if not args.yes:
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

    removed = history.reset_seller(
        seller,
        backup=True,
    )
    history.save()
    print(
        f"Reset complete. Removed {removed} recorded listing ID(s)."
    )
    print(
        "A timestamped history backup was created in the data folder."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
