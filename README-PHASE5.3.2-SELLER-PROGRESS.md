# Phase 5.3.2 — Seller Radar Next-Unscanned Progress

## New default behaviour

`sellerRadar.bat` now treats the number entered as:

```text
Number of NEW unscanned listings to analyse
```

Example:

```text
Seller has 300 active Pokémon listings
First run requests 30  → listings 1–30 are analysed and recorded
Second run requests 30 → previously recorded IDs are skipped; 30 unseen listings are analysed
Third run requests 30  → the next unseen batch is analysed
```

The exact order can change when eBay adds new listings or old auctions end.
The tool therefore does not rely on a fragile numeric offset. It always starts
from the seller's current ending-soonest inventory and skips every eBay Item ID
already stored for that seller.

This guarantees that active listings are not analysed twice unless the history
is deliberately reset.

## What is remembered

The file:

```text
data\seller-radar-scan-history.json
```

stores, per seller:

- eBay Item ID;
- title;
- first and latest scan timestamps;
- batch/run ID;
- whether the listing matched the card database;
- financial decision or unmatched reason;
- listing format;
- compact run history.

It does not contain eBay credentials or passwords.

Matched, unmatched and excluded listings are all recorded as scanned. This is
important: vague lots or graded listings will not reappear in every later batch.

## Pagination

The scanner fetches pages of up to 200 seller listings and continues until it:

- collects the requested number of unseen listings;
- reaches the end of the current active inventory; or
- reaches the page-safety limit.

Optional setting:

```text
SELLER_RADAR_MAX_SEARCH_PAGES=25
```

The default permits inspection of up to 5,000 API-visible listings while still
analysing only the requested unseen batch.

## Seller worksheet summary

The dedicated seller tab now also displays:

```text
Batch number
Previously scanned
New batch
Listings examined
Skipped seen
History after
Inventory status
```

The tab continues to show only the latest analysed batch. The persistent JSON
file controls progress across all runs.

## No unseen listings

When every currently API-visible Pokémon listing for that seller is already in
history:

- the BAT reports `NO UNSCANNED ACTIVE LISTINGS`;
- no duplicate analysis is performed;
- the existing seller worksheet is left unchanged.

New listings posted later are automatically considered unseen.

## Reset one seller

Run:

```text
resetSellerRadarHistory.bat
```

Enter the seller username and confirm with:

```text
RESET SELLER
```

The next Seller Radar run then begins again from that seller's first currently
active listings. A timestamped backup of the history file is created before the
reset.

## Installation

1. Extract the add-on ZIP.
2. Copy all files into the existing scanner folder.
3. Replace existing Seller Radar files.
4. Run:

```text
install-seller-radar-progress-upgrade.bat
```

5. Continue using:

```text
sellerRadar.bat
```
