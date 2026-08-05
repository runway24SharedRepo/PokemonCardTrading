# Phase 5.4.2 — Seller Radar History Numbered Selector

## New reset workflow

Run:

```text
resetSellerRadarHistory.bat
```

The tool reads:

```text
data\seller-radar-scan-history.json
```

and lists every seller currently tracked by Seller Radar.

Example:

```text
1) antonio  [30 listings, 1 batch]
2) alex     [90 listings, 3 batches]
3) fabien   [60 listings, 2 batches]
4) lotto    [120 listings, 4 batches]

Which seller history should be removed? (example 3;4):
```

## Supported selections

```text
3;4     sellers 3 and 4
1,3     sellers 1 and 3
1 3     sellers 1 and 3
2-4     sellers 2, 3 and 4
A       every tracked seller
Q       cancel
```

Duplicate numbers are ignored safely. Reversed ranges such as `4-2` are
accepted as sellers 2 through 4.

## Confirmation and safety

Before anything is removed, the tool prints the selected sellers, listing
counts and batch counts.

Confirmation requires:

```text
RESET SELECTED
```

One timestamped backup of the complete history file is created before the
multi-seller reset.

The operation removes only persistent Seller Radar progress. It does not delete:

- seller worksheets;
- scan results already visible in Excel;
- market data;
- Watchlist data;
- eBay credentials.

The next `sellerRadar.bat` run for a reset seller begins again from that
seller's first currently active API-visible listings.

## Installation

1. Extract the add-on ZIP.
2. Copy the files into the main scanner folder.
3. Replace the existing files.
4. Run:

```text
install-phase5.4.2-seller-history-selector.bat
```

5. Use:

```text
resetSellerRadarHistory.bat
```
