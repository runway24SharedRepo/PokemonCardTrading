from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ebay_watchlist import (
    EbayWatchlistClient,
    ManagedWatchlistLedger,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Manage the eBay Watchlist used by the scanner."
    )
    value.add_argument("--managed", action="store_true")
    value.add_argument("--all", action="store_true")
    value.add_argument("--status", action="store_true")
    value.add_argument("--yes", action="store_true")
    return value


def interactive_choice() -> str:
    print()
    print("Choose the cleanup operation:")
    print()
    print("  1 - Remove only listings added by this scanner")
    print("      Safe default. Manually watched eBay items are preserved.")
    print()
    print("  2 - REMOVE EVERY ITEM FROM THE EBAY WATCHLIST")
    print("      This also removes items you added manually on eBay.")
    print()
    print("  3 - Show Watchlist status only")
    print()
    print("  Q - Cancel")
    print()
    return input("Selection [1]: ").strip().upper() or "1"


def main() -> int:
    args = parser().parse_args()
    root = Path(__file__).resolve().parent
    load_dotenv(
        root / ".env",
        override=True,
        encoding="utf-8-sig",
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("ebay-watchlist-manager")
    client = EbayWatchlistClient(logger)
    ledger = ManagedWatchlistLedger(
        root / "data" / "ebay-watchlist-managed.json"
    )

    if not client.configured:
        print(
            "ERROR: No user-authorised eBay token is configured."
        )
        print(
            "Run configure-ebay-watchlist-auth.bat, then add one of:"
        )
        print("  EBAY_USER_REFRESH_TOKEN")
        print("  EBAY_USER_ACCESS_TOKEN")
        print("  EBAY_AUTH_TOKEN")
        return 1

    choice = ""
    if args.managed:
        choice = "1"
    elif args.all:
        choice = "2"
    elif args.status:
        choice = "3"
    else:
        choice = interactive_choice()

    try:
        print()
        print(
            f"Authentication mode: {client.authentication_mode}"
        )

        if choice in {"Q", "QUIT", "CANCEL"}:
            print("Cancelled. No eBay items were changed.")
            return 0

        if choice == "3":
            count, maximum = client.get_watchlist_count()
            print(f"Current eBay Watchlist items: {count}")
            if maximum is not None:
                print(f"Watchlist maximum: {maximum}")
            print(
                "Scanner-managed active items recorded locally: "
                f"{len(ledger.active_ids())}"
            )
            return 0

        if choice == "1":
            active_ids = ledger.active_ids()
            if not active_ids:
                print(
                    "There are no active scanner-managed Watchlist "
                    "items in the local ledger."
                )
                return 0

            print(
                f"Scanner-managed items to remove: {len(active_ids)}"
            )
            if not args.yes:
                confirmation = input(
                    "Type REMOVE MANAGED to continue: "
                ).strip()
                if confirmation != "REMOVE MANAGED":
                    print("Cancelled. No eBay items were changed.")
                    return 0

            removed: list[str] = []
            final_count = None
            final_maximum = None

            for batch, result in client.remove_item_ids(active_ids):
                removed.extend(batch)
                final_count = result.watchlist_count
                final_maximum = result.watchlist_maximum

            ledger.mark_removed(removed)
            ledger.save()

            print(
                f"Removed/confirmed scanner-managed items: "
                f"{len(removed)}"
            )
            if final_count is not None:
                print(
                    f"eBay Watchlist now: {final_count}"
                    + (
                        f"/{final_maximum}"
                        if final_maximum is not None
                        else ""
                    )
                )
            print(
                "Manually watched items that were not added by the "
                "scanner were preserved."
            )
            return 0

        if choice == "2":
            print()
            print("DANGER: This removes EVERY item from My eBay Watchlist.")
            print(
                "It includes listings added manually, by the scanner, "
                "or by any other application."
            )
            if not args.yes:
                confirmation = input(
                    "Type DELETE ALL to continue: "
                ).strip()
                if confirmation != "DELETE ALL":
                    print("Cancelled. No eBay items were changed.")
                    return 0

            result = client.remove_all_items()
            ledger.mark_removed(ledger.active_ids())
            ledger.save()

            print("The entire eBay Watchlist was cleared.")
            if result.watchlist_count is not None:
                print(
                    f"eBay Watchlist now: {result.watchlist_count}"
                    + (
                        f"/{result.watchlist_maximum}"
                        if result.watchlist_maximum is not None
                        else ""
                    )
                )
            return 0

        print("Unknown selection. No eBay items were changed.")
        return 2

    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
