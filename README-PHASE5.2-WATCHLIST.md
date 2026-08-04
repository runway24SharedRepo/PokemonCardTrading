# Phase 5.2 — eBay Watchlist Integration

## What changes

The existing daily launchers remain unchanged:

```text
run-random-range-sniper.bat
run-live.bat
```

At the end of each successful scan, financially GREEN listings are added to
the authorised user's My eBay Watchlist.

This includes:

- normal GREEN scanner results;
- GREEN same-seller discoveries;
- GREEN auctions;
- GREEN Buy It Now listings that use a supported single-item identifier.

The financial condition logic is not changed. A listing can therefore be:

```text
Decision: GREEN
Condition Flag: RED
```

and still enter the Watchlist for manual photograph inspection.

## User authorisation is required

The Browse scanners use an application token. A personal Watchlist change must
be authorised by the eBay user.

Run:

```text
configure-ebay-watchlist-auth.bat
```

The helper adds the required `.env` settings, opens `.env`, then tests the
Watchlist connection.

Configure one of these methods:

### Preferred

```text
EBAY_USER_REFRESH_TOKEN=<production OAuth user refresh token>
```

### Temporary test

```text
EBAY_USER_ACCESS_TOKEN=<production OAuth user access token>
```

A temporary access token expires and must be replaced.

### Traditional Trading API alternative

```text
EBAY_AUTH_TOKEN=<production Auth'n'Auth user token>
```

Never upload or share `.env`.

## Watchlist settings

```text
EBAY_WATCHLIST_ENABLED=YES
EBAY_WATCHLIST_MAX_ADD_PER_RUN=50
EBAY_WATCHLIST_RECHECK_HOURS=6
EBAY_WATCHLIST_BATCH_SIZE=25
EBAY_WATCHLIST_TIMEOUT_SECONDS=30
EBAY_TRADING_SITE_ID=3
EBAY_TRADING_COMPATIBILITY_LEVEL=1455
```

The scanner records its successfully managed items in:

```text
data/ebay-watchlist-managed.json
```

This contains listing identifiers and titles, not account credentials.

## Cleanup

Run:

```text
cleanWatchlist.bat
```

The interactive choices are:

### 1 — scanner-managed only

Removes only items recorded as added by this scanner.

This is the safe default and preserves manually watched items.

### 2 — entire eBay Watchlist

Uses eBay's RemoveAllItems operation.

It removes:

- scanner-added items;
- manually watched items;
- items added by any other application.

The destructive operation requires typing:

```text
DELETE ALL
```

### 3 — status only

Displays the current Watchlist count and the number of active scanner-managed
items recorded locally.

## Multi-variation listings

eBay requires additional variation-specific data to watch a particular option
inside a multi-variation fixed-price listing. These uncommon listings are
skipped automatically and clearly marked in the spreadsheet Notes column.

## Failure behaviour

Watchlist synchronisation is non-fatal.

If the user token is missing, expired or rejected:

- scanner results are still saved;
- Excel is still updated;
- the console and log explain the Watchlist problem;
- no credentials are printed.

## Installation

1. Extract this ZIP.
2. Copy every file into the existing scanner folder.
3. Replace files when prompted.
4. Run:

```text
install-phase5.2-watchlist-upgrade.bat
```

5. Run:

```text
configure-ebay-watchlist-auth.bat
```

6. Continue using the normal scanner BAT files.
