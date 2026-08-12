# Phase 5.7.5 — Multi-Path API Recovery

This hotfix corrects the low pricing coverage seen when the Pokemon TCG API
intermittently returns HTTP 500/502 responses. Phase 5.7.4 retried the same
single-card URL three times; repeated failures on that route still produced
poor coverage.

## New runtime behaviour

- Each uncached card receives three progressively broader request paths:
  compact single-card response, full single-card response, then the
  collection endpoint queried by exact card ID.
- Every response is validated against the requested card ID before use.
- HTTP `429/500/502/503/504`, timeouts and connection failures move to the
  next controlled path.
- Attempts use short exponential backoff with jitter (normally about 1 and 2
  seconds before the second and third requests).
- Retry activity is logged as `INFO`, not as repeated warnings.
- `ON-DEMAND PRICE UNAVAILABLE` is emitted once, only when all attempts fail.
- A success on attempt 2 or 3 is immediately saved in the shared 24-hour
  SQLite cache.
- A final failure is eligible for a new attempt after 60 seconds by default,
  instead of being suppressed for 15 minutes.
- Installation clears old failed-price checkpoints so previously
  missing cards are eligible immediately, while successful cached prices are
  preserved.
- After five consecutive cards exhaust all their retries, the existing
  circuit breaker defers further uncached cards for 15 minutes. Successful
  responses reset the consecutive-failure count.
- The run summary separates API calls, retry calls, prices recovered by a
  retry, alternate-path recoveries and final network failures.

## Pricing rules unchanged

- Standard/Holofoil uses `cardmarket.prices.avg30`.
- Reverse Holofoil uses `cardmarket.prices.reverseHoloAvg30`.
- First Edition, Shadowless and unsafe variant matches remain unavailable.
- Stored workbook prices, TCGplayer market, `averageSellPrice`, trend, AI and
  stale cached responses are never substituted.

## Cache

Successful responses are shared for 24 hours at:

```text
data\on-demand-price-cache.sqlite
```

This cache means a recovered price is reused by Live Radar, Random Range
Sniper and Seller Radar without another API request that day.

## Install

1. Close Excel and every scanner BAT window.
2. Copy the package contents into the main `PokemonCardTrading` folder.
3. Run `install-phase5.7.5-multi-path-api-recovery.bat`.
4. Start the desired scanner normally.

The isolated installer test runs before any source files are replaced and
saves its output under `logs\phase5.7.5-install-test-YYYYMMDD-HHMMSS.log`.

Optional `.env` settings:

```text
ON_DEMAND_PRICE_CACHE_TTL_SECONDS=86400
ON_DEMAND_PRICE_FAILURE_COOLDOWN_SECONDS=60
ON_DEMAND_PRICE_CIRCUIT_FAILURES=5
ON_DEMAND_PRICE_CIRCUIT_COOLDOWN_SECONDS=900
ON_DEMAND_PRICE_RETRY_ATTEMPTS=3
```
