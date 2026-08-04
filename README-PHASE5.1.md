# Phase 5.1 — Link Layout and eBay Quota Checker

## Link-column relocation

The scanning algorithms are unchanged.

### Random Snipe Results and Random Snipe Queue

The clickable columns now appear immediately after:

```text
Market (£)
Bid / Market
Buy Now / Market
```

The link group is:

```text
Direct Listing
Card Image
Auction Search
Buy Now Search
Sold Comparables
```

### Live Opportunities

The clickable columns now appear immediately after:

```text
Market (£)
Cost / Market
```

The link group is:

```text
Direct Listing
Card Image
Auction Search
Sold Comparables
```

This reduces horizontal scrolling during review.

## Installation

1. Extract this ZIP.
2. Copy all files and folders into the existing scanner folder.
3. Choose **Replace the files in the destination**.
4. Close Excel.
5. Run:

```text
install-phase5.1-layout-upgrade.bat
```

The installer creates a timestamped workbook backup.

The current result tables are cleared because their column order changes.
Random Snipe History, the market database, settings and credentials remain.

An existing non-empty Opportunity Archive is renamed to:

```text
Opportunity Archive Legacy
```

A fresh archive with the new column order is created.

## Daily API quota checker

Run:

```text
check-ebay-query-limits.bat
```

It reads the existing production credentials from `.env` and reports the
application-level eBay Buy/Browse rate-limit records:

- limit;
- used/count;
- remaining;
- reset time;
- time window.

It does not open or modify Excel and it does not perform a Browse item search.

The output is also saved to:

```text
ebay-api-limits.log
```
