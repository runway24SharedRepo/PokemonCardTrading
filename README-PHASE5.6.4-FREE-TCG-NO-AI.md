# Phase 5.6.4 — Free TCG Market Pricing, No AI

This rollback restores the original free Pokémon TCG market-price pipeline and
disconnects the OpenAI integration from the scanner project.

## Pricing authority

Market Data Import column H is populated by the daily market updater:

1. TCGplayer's exact variant-specific market value from the Pokémon TCG API.
2. Other TCGplayer values only according to the configured priority.
3. Cardmarket only when TCGplayer has no value for that exact variant.
4. A verified manual override from Market Price Controls, when present.

Live Radar, Random Range Sniper and Seller Radar read the same column H. They do
not contact OpenAI and do not replace the imported market value.

## Installation

1. Close Excel.
2. Copy this folder's contents into the main PokemonCardTrading folder and
   choose Replace files in destination.
3. Run install-phase5.6.4-free-tcg-no-ai.bat.
4. Run update-pokemon-market-daily.bat.
5. Use run-live.bat or run-random-range-sniper.bat normally.

The installer removes OpenAI and AI-market settings from .env, but preserves
all eBay and Pokémon TCG settings. Old AI files and caches are moved into a
timestamped folder under backups so the change is recoverable.

The restart-safe Live Radar improvements remain:

- persistent listing-title identification cache;
- detailed progress and ETA messages;
- safe staging workbook;
- completed title identifications survive Ctrl+C or a closed BAT window.

## Important limitation

The free Pokémon TCG feed supplies raw card variant prices. It does not provide
reliable grade-specific prices, complete lot values or proxy prices. The
original exclusions therefore apply again so those products cannot be scored
against an inappropriate raw-card value.
