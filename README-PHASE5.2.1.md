# Phase 5.2.1 — Watchlist Cleaner hotfix

This fixes eBay Trading API error `20820` during **Delete All**.

The cleaner now:

1. Calls `GetMyeBayBuying` to read the authorised account's Watchlist.
2. Reports success when the API-visible Watchlist is already empty.
3. Tries eBay's normal `RemoveAllItems=true` operation.
4. If eBay returns error `20820`, retrieves the actual watched ItemIDs and removes them in batches.
5. Retries failed batches one item at a time so one stale or unusual listing does not block the rest.
6. Verifies the remaining Watchlist count after cleanup.

## Install

Copy these files into the existing scanner folder and replace the old versions:

- `ebay_watchlist.py`
- `manage_ebay_watchlist.py`
- `cleanWatchlist.bat`
- `install-phase5.2.1-hotfix.bat`

Run:

```text
install-phase5.2.1-hotfix.bat
```

Then run:

```text
cleanWatchlist.bat
```

If the cleaner reports that the API-visible Watchlist is empty while the eBay website still shows watched items, the Auth'n'Auth token belongs to a different eBay account from the one open in the browser.
