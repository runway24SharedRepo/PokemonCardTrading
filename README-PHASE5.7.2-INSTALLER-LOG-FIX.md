# Phase 5.7.2 — Installer Logging and Windows Test Fix

This hotfix keeps the Phase 5.7.1 pricing and cache behaviour unchanged. It
repairs the installer regression suite on Windows and guarantees that a failed
installation leaves both a readable console message and a timestamped log.

## What was fixed

- Every test resolver closes its SQLite connection before its temporary
  directory is removed. This prevents Windows file-lock cleanup errors.
- The installer tests the packaged payload in an isolated temporary cache,
  rather than touching `data\on-demand-price-cache.sqlite` in the live project.
- The complete regression output is saved under `logs\` and printed back to
  the installer window.
- Success and failure paths both pause, so the window cannot disappear before
  the result and log path are read.
- The payload is tested before any installed source file is replaced.
- Partial copying is detected and causes a clear failure.

The on-demand pricing rules, 24-hour success cache, failure cooldown and
circuit breaker remain as documented below.

Phase 5.7 removes `Market Data Import!H` as the scanner's price authority.

## Runtime flow

1. The scanner downloads active eBay listings.
2. The existing identity index matches each title to an exact Pokemon TCG API
   card ID, set, collector number and variant.
3. The first matched listing for each unique card checks the durable 24-hour
   cache. Only a missing or expired card triggers
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

## Freshness, resume and outage handling

- Successful API card responses are stored in
  `data\on-demand-price-cache.sqlite` for 24 hours.
- All scanner modes share that cache. A successful price fetched by Live Radar
  can therefore be reused by Random Range Sniper or Seller Radar on the same
  day.
- The same card is requested only once within a run, even if many listings use
  it.
- HTTP/API failures receive a retry-after checkpoint. The scanner does not
  pause for four retries on every failed card.
- After five consecutive provider failures, a 15-minute circuit breaker opens
  and remaining uncached cards are deferred. Valid 24-hour cache entries still
  work while the circuit is open.
- A later run resumes naturally: valid successes are reused and only expired,
  missing or retry-eligible cards contact the API.
- An expired cached response is never used when its refresh fails.
- No workbook price is used as a fallback.
- The result records Cardmarket's `updatedAt` date. Re-querying cannot make the
  provider's underlying price guide newer than that date.
- Logs report `PRICE PROGRESS` with checked, available, unavailable, cache-hit,
  API-call and deferred counts.

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
3. Run `install-phase5.7.2-installer-log-fix.bat`.
4. Start a normal scan. A daily market-table refresh is not required.

If installation fails, open the exact log path printed by the installer. Logs
are stored in `logs\phase5.7.2-install-test-YYYYMMDD-HHMMSS.log`.

The defaults can be changed in `.env` only if needed:

```text
ON_DEMAND_PRICE_CACHE_TTL_SECONDS=86400
ON_DEMAND_PRICE_FAILURE_COOLDOWN_SECONDS=900
ON_DEMAND_PRICE_CIRCUIT_FAILURES=5
ON_DEMAND_PRICE_CIRCUIT_COOLDOWN_SECONDS=900
ON_DEMAND_PRICE_RETRY_ATTEMPTS=1
```
