# Phase 5.6.7 — 30-Day Average Selling Price Authority

This hotfix changes the scanner's valuation authority from Cardmarket's
non-windowed `averageSellPrice` to its rolling 30-day average selling price.

## Column H

`Market Data Import!H` is labelled **Average Selling Price (£)** and uses:

- standard Unlimited Normal or Holofoil: `cardmarket.prices.avg30`;
- Reverse Holofoil: `cardmarket.prices.reverseHoloAvg30`;
- EUR converted to GBP with the one documented EUR-to-GBP rate obtained at the
  start of the update.

The updater never substitutes `averageSellPrice`, `reverseHoloSell`,
`trendPrice`, `avg1`, `avg7`, a TCGplayer `market` value, or any high/mid/low
field. Those supporting fields remain audit-only.

Cardmarket does not expose a distinct First Edition average in this API
payload. First Edition and any finish that cannot be isolated safely are
therefore marked `PRICE UNAVAILABLE`. A verified manual override can still be
used deliberately through `Market Price Controls`.

## Calculation chain

Live Radar, Random Range Sniper, Seller Radar and long-term analysis already
read column H by position. Their discounts, target delivered prices, maximum
bids, profit estimates, rankings and scores therefore use the corrected
average selling price without changing the compatible A–L column layout.

Old TCGplayer market and Phase 5.6.6 non-windowed average history are tagged as
different metrics and excluded from the new comparison baseline. They are not
deleted.

## Install

1. Close Excel and stop scanner BAT files.
2. Copy this package into the main `PokemonCardTrading` folder.
3. Run `install-phase5.6.7-30-day-average-selling-price.bat`.
4. Run `update-pokemon-market-daily.bat`.

Pikachu `base1-58` and Palkia `dp5-11` are included as acceptance fixtures.
Their standard values are read from `cardmarket.prices.avg30`; reverse-holo
values are read only from `reverseHoloAvg30`.

The Pikachu fixture deliberately contains the anomalous non-windowed value
`averageSellPrice = EUR 23.99`. The test rejects it, selects `avg30 = EUR
6.21`, and converts it at 0.857050 GBP/EUR to **GBP 5.32**.
