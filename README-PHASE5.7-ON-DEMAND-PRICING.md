# Phase 5.7 — On-Demand 30-Day Pricing

Phase 5.7 removes `Market Data Import!H` as the scanner's price authority.

## Runtime flow

1. The scanner downloads active eBay listings.
2. The existing identity index matches each title to an exact Pokemon TCG API
   card ID, set, collector number and variant.
3. The first matched listing for each unique card triggers
   `GET https://api.pokemontcg.io/v2/cards/{card-id}`.
4. The scanner reads only:
   - standard printed finish: `cardmarket.prices.avg30`;
   - Reverse Holofoil: `cardmarket.prices.reverseHoloAvg30`.
5. One EUR-to-GBP rate is obtained for the scan run.
6. The fresh GBP result is used for the target, ratio, maximum bid, headroom,
   opportunity decision, ranking and long-term assessment.

The direct Cardmarket API is not required. Cardmarket is currently not
accepting new API-access applications. The scanner uses the Cardmarket price
fields embedded in the free Pokemon TCG API card response.

## Freshness and caching

- Every BAT run starts with an empty price cache.
- The same card is requested only once within that run, even if it appears in
  many eBay listings.
- No workbook price and no previous-run cached price is used as a fallback.
- The result records Cardmarket's `updatedAt` date. Re-querying cannot make the
  provider's underlying price guide newer than that date.

## Safety rules

- TCGplayer `market`, Cardmarket `averageSellPrice`, `trendPrice`, `avg1`,
  `avg7`, high/mid/low and AI values never enter the financial calculation.
- First Edition, Shadowless or another edition/finish that the Cardmarket
  payload cannot isolate is `PRICE UNAVAILABLE` and is not scored.
- If the Pokemon TCG API, exchange-rate service or exact field is unavailable,
  the listing is skipped rather than assessed with an old or substituted
  value.
- Cards not encountered in the run retain their existing portfolio value;
  they are not overwritten with zero.

## Scanner modes

- `run-live.bat`: prices exact matched broad-radar and seller-expansion cards.
- `run-random-range-sniper.bat`: lazily prices candidate cards, applies the
  configured GBP range to the fresh value, then searches eBay.
- `sellerRadar.bat`: prices every exact matched seller listing before scoring.
- Reroll-only mode also obtains current prices so its configured range remains
  meaningful.

`update-pokemon-market-daily.bat` remains available for catalogue and audit
work, but it is no longer required before a scan and its column-H values are
not used by Phase 5.7 scanner calculations.

## API key

The Pokemon TCG API works without a key but has much lower limits. Keep the
existing optional entry in `.env`:

```text
POKEMON_TCG_API_KEY=your_free_key
```

## Install

1. Close Excel and every scanner BAT window.
2. Copy this package into the main `PokemonCardTrading` folder.
3. Run `install-phase5.7-on-demand-30-day-pricing.bat`.
4. Start a normal scan. A daily market-table refresh is not required.

