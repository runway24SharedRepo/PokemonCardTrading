# Phase 5.4 — UK and Global Pokémon Market Links

This upgrade adds four clickable card-specific price references immediately
after `Sold Comparables`:

```text
UK Market
TCGplayer
Cardmarket
PriceCharting
```

## UK link

`UK Market` opens CardMetric UK using the identified card name, set, collector
number and variant. CardMetric focuses on GBP and UK sold-market information.

## Global links

- `TCGplayer` — United States marketplace and market-price reference;
- `Cardmarket` — European marketplace and EUR price trends;
- `PriceCharting` — raw and graded historical price guide.

These are reference checks only. They do not replace the scanner's configured
market value or alter GREEN/AMBER/RED decisions.

## Worksheets covered

- Random Range Sniper selected-card table;
- Random Snipe Results;
- Random Snipe Queue;
- Random Snipe History;
- legacy Snipe Queue;
- Live Opportunities;
- Opportunity Archive;
- every existing and future `Seller - ...` worksheet.

All four links use the exact identified card details. Unmatched Seller Radar
listings do not receive market links because the scanner deliberately has not
identified a safe card match.

## Installation

1. Extract the ZIP.
2. Copy every file and folder into the main scanner directory.
3. Replace existing files when prompted.
4. Close Excel.
5. Run:

```text
install-phase5.4-market-links-upgrade.bat
```

The installer creates a timestamped workbook backup and upgrades existing
worksheets in place. Historical rows and seller statuses are preserved.

Continue using the existing BAT files:

```text
run-random-range-sniper.bat
run-live.bat
sellerRadar.bat
```
