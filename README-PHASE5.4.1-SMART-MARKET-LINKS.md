# Phase 5.4.1 — Smart Market-Link Search

## Problem corrected

The original market links used:

```text
Card name + set name + collector number + variant
```

Example:

```text
Kyogre-EX XY Black Star Promos XY41
```

Some market trackers return no result because the query contains too many
database-specific words and punctuation.

## New canonical query

Every market tracker now uses:

```text
clean card name + collector number/ID
```

Examples:

```text
Kyogre-EX | XY Black Star Promos | XY41
→ Kyogre EX XY41

N's Zekrom | Ascended Heroes | 155
→ Ns Zekrom 155

Pikachu | Base Set | 58/102
→ Pikachu 58

Pikachu | Cosmic Eclipse | TG06/TG30
→ Pikachu TG06
```

## Cleaning rules

- set name is omitted;
- variant is omitted;
- hyphens become spaces;
- apostrophes are removed;
- other punctuation becomes spaces;
- repeated spaces are collapsed;
- accents are converted to plain searchable characters;
- `♀` becomes `F`;
- `♂` becomes `M`;
- slash collector numbers use the left-hand identifier;
- when card number is empty, a compact final token from Card ID is used.

All four links receive the same compact query:

```text
UK Market
TCGplayer
Cardmarket
PriceCharting
```

## Installation

1. Extract the ZIP.
2. Copy all files into the main scanner folder.
3. Replace `market_links.py` and `upgrade_phase5_4_market_links.py`.
4. Close Excel.
5. Run:

```text
install-phase5.4.1-smart-market-links.bat
```

The installer:

- creates a timestamped workbook backup;
- refreshes existing links on Random, Live, archive and Seller tabs;
- updates the runtime generator used by all future scans.

No market data, seller progress, Watchlist data or scanner settings are changed.
