# Phase 5.5.3 — Edition-Safe Pricing

## Corrected example

```text
Pokémon Magnemite 53/102 Base Set WOTC 1999 Unlimited Common TCG Card
```

The listing now uses:

```text
Magnemite | Base | 53 | Normal
standard/Unlimited market value
```

It cannot use a First Edition value unless the title explicitly says
`1st Edition`, `First Edition` or `1st Ed`.

## What changed

- Unmarked vintage listings default to standard/Unlimited.
- `Unlimited` is a hard conflict for every First Edition candidate.
- First Edition candidates require explicit title evidence.
- Shadowless candidates also require explicit wording.
- One-variant-per-card no longer favours First Edition because of sort order.
- For cards with separate First Edition prices, TCGplayer `normal` and
  `holofoil` are used for standard/Unlimited variants.
- Cardmarket's broad Normal trend does not override edition-specific prices.
- Unsafe standard rows with no edition-specific price are disabled.
- Actual eBay listing photographs are preferred.
- Generic database images are suppressed for edition-sensitive cards.

## Existing workbook repair

The installer updates existing `Market Data Import` rows using edition-specific
USD prices already stored in `Full Card Database`.

A timestamped backup is created under:

```text
backups\phase5.5.3
```

## Future updates

The included replacement:

```text
market_updater\pricing.py
```

applies the same rules whenever `update-pokemon-market-daily.bat` runs.

## Installation

1. Extract the add-on.
2. Copy every file and folder into the main `PokemonCardTrading` directory.
3. Replace existing files.
4. Close Excel.
5. Run:

```text
install-phase5.5.3-edition-safe-pricing.bat
```

6. Rerun Random, Live and Seller Radar.

Existing archive/history records are preserved.
