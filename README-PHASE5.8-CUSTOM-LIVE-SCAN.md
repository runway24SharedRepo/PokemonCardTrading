# Phase 5.8.2 — Excel COM Worksheet-Copy Hotfix

This hotfix repairs the Excel COM failure raised while opening `Custom Live
Results` or `Custom Live Queue`. Worksheet names are resolved through the
workbook collection with whitespace normalisation, and copied tabs are checked
before any result write begins.

Phase 5.8.2 additionally replaces the unreliable named `After=` COM argument
with positional `Worksheet.Copy(Before, After)` arguments. If Excel still does
not copy the worksheet, it creates the tab explicitly and copies the template's
used cells and column widths.

Phase 5.8 adds `liveScanCustom.bat`, a live UK eBay scan controlled by a small
text file rather than random card selection.

## Input

Edit `pokemonInput.txt` and add one `Market Data Import` column-H cell per line:

```text
H1810
H1811
```

For each selected row, the scanner reads:

| Column | Meaning |
| --- | --- |
| B | Card name |
| C | Set |
| D | Card number |
| E | Variant |
| F | Language |
| H | Manual reference market cost |

The text-file selection overrides column A. Blank lines, duplicate references
and comments beginning with `#` are supported. Invalid rows stop the run before
the real workbook is replaced.

## Scan behaviour

- One exact eBay query is run for every selected card.
- Returned titles are validated against exact card name, set, number and
  variant.
- The value currently stored in column H is the only price authority for this
  custom mode.
- Item plus delivery is compared with the target purchase ratio configured on
  `Random Range Sniper`.
- Listing format, ending window, seller-feedback threshold and postage limit
  are also inherited from `Random Range Sniper`.
- Random selection, market-value range filters, replacement cards and seller
  expansion are disabled.
- No Cardmarket/API price lookup is performed by this custom mode.
- No eBay Watchlist/list write is performed.

## Output

The first successful run creates two sheets by copying the existing workbook
templates:

- `Custom Live Results`
- `Custom Live Queue`

Run history also receives a `CUSTOM` entry. The workbook is updated through a
staging copy and is replaced only after the complete scan succeeds.

## Installation

1. Install Phase 5.7.6 first.
2. Close Excel and every scanner BAT window.
3. Copy this package into the main `PokemonCardTrading` folder.
4. Run `install-phase5.8.2-excel-com-copy-hotfix.bat`.
5. Edit `pokemonInput.txt`.
6. Run `liveScanCustom.bat`.

The activity log is `custom-live-scan.log`.
