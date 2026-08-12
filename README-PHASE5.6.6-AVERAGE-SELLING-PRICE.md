# Phase 5.6.6 — Average Selling Price Authority

This hotfix changes the scanner's valuation authority from TCGplayer market
value to Cardmarket average selling price returned inside each Pokémon TCG API
card record.

## Column H

`Market Data Import!H` is labelled **Average Selling Price (£)** and uses:

- standard Unlimited Normal or Holofoil: `cardmarket.prices.averageSellPrice`;
- Reverse Holofoil: `cardmarket.prices.reverseHoloSell`;
- EUR converted to GBP with the one documented EUR-to-GBP rate obtained at the
  start of the update.

The updater never substitutes `trendPrice`, `avg1`, `avg7`, `avg30`, a
TCGplayer `market` value, or any high/mid/low field. Those supporting fields
remain audit-only.

Cardmarket does not expose a distinct First Edition average in this API
payload. First Edition and any finish that cannot be isolated safely are
therefore marked `PRICE UNAVAILABLE`. A verified manual override can still be
used deliberately through `Market Price Controls`.

## Calculation chain

Live Radar, Random Range Sniper, Seller Radar and long-term analysis already
read column H by position. Their discounts, target delivered prices, maximum
bids, profit estimates, rankings and scores therefore use the corrected
average selling price without changing the compatible A–L column layout.

Old TCGplayer market history is tagged as a different metric and excluded from
the new comparison baseline. It is not deleted.

## Install

1. Close Excel and stop scanner BAT files.
2. Copy this package into the main `PokemonCardTrading` folder.
3. Run `install-phase5.6.6-average-selling-price.bat`.
4. Run `update-pokemon-market-daily.bat`.

Palkia `dp5-11` is included as the acceptance fixture. Its Holofoil value is
read from `cardmarket.prices.averageSellPrice`, not from TCGplayer market or
Cardmarket trend.
