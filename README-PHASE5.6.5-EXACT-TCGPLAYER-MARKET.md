# Phase 5.6.5 — Exact TCGplayer Market Value

This hotfix makes the free Pokémon TCG API the sole automatic source of
scanner market values.

## Exact pricing rules

- Uses only `tcgplayer.prices.<exact category>.market`.
- Keeps Normal, Holofoil, Reverse Holofoil, First Edition and Unlimited
  identities separate.
- Never chooses the largest price.
- Never substitutes `high`, `mid`, `low`, `directLow` or Cardmarket data.
- Records `PRICE UNAVAILABLE` and leaves the scanner value blank when the
  exact market field is absent.
- Keeps verified values in `Market Price Controls` as deliberate overrides.

The official categories are `normal`, `holofoil`, `reverseHolofoil`,
`1stEditionNormal` and `1stEditionHolofoil`. The updater also accepts an
explicit vintage `unlimited` category as Unlimited Normal only when the card
record is non-holo. Ambiguous generic vintage categories are never guessed.

## Eevee acceptance test

Fixture: Eevee — Jungle — 51/64 — Normal — Unlimited (`base2-51`).

- Selected path: `tcgplayer.prices.unlimited.market`
- USD market: `$2.94`
- Test FX: `1 GBP = 1.3479 USD`
- Converted value: `£2.18`
- The First Edition value is retained as a separate row and never selected for
  Unlimited.

## Workbook compatibility

Columns A–L of `Market Data Import` retain the positions used by Live Radar,
Random Range Sniper and Seller Radar. Column H remains their numeric value.
Audit fields are appended through column Z.

The updater downloads each API page once, reuses the records for every matching
row, saves page checkpoints, and resumes interrupted downloads. Excel is
updated through a staging copy; the real dashboard is replaced only after the
complete workbook saves successfully.

## Install

1. Close Excel and stop scanner BAT files.
2. Copy this hotfix folder's contents into the main `PokemonCardTrading`
   folder.
3. Run `install-phase5.6.5-exact-tcgplayer-market.bat`.
4. Run `update-pokemon-market-daily.bat`.
5. Review `Market Update Summary` and `Market Data Import`.
