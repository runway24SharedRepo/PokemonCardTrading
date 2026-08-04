# Phase 4.1 — Decimal Card Number Fix and Random Snipe Queue

## Fixes

Excel can expose whole-number card identifiers as floating-point values.
Phase 4.1 converts:

```text
54.0 → 54
```

before building exact active and sold eBay search links.

Identifiers such as these remain unchanged:

```text
054
RC10
TG06
58/102
```

## Output behaviour

### Random Snipe Results

Contains every reliably matched live UK eBay auction returned for the selected
random cards. A listing remains visible even when it ends outside the configured
sniping window.

### Random Snipe Queue

Contains the immediate-action subset whose ending time is inside the configured
`Ending within` window.

Every queue row includes clickable:

- Direct Listing
- Active Search
- Sold Comparables
- Card Image

### Existing Snipe Queue

When `Copy GREEN to Snipe Queue` is YES, only GREEN rows from the Random Snipe
Queue are copied into the existing general Snipe Queue.

## Upgrade an existing Phase 4 installation

1. Extract the Phase 4.1 ZIP.
2. Copy all files and folders into the existing scanner folder.
3. Choose Replace when Windows asks.
4. Close Excel.
5. Run:

```text
install-phase4.1-upgrade.bat
```

6. Run:

```text
run-random-range-sniper.bat
```

The upgrade creates a timestamped workbook backup and preserves the existing
Random Snipe History.
