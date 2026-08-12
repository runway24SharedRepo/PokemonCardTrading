from __future__ import annotations

import json
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests

from market_updater.api import fetch_fx_rates
from market_updater.pricing import FxRates, PriceVariant, build_price_variants


@dataclass(frozen=True)
class PriceQuote:
    card_id: str
    variant: str
    price_gbp: float | None
    price_eur: float | None
    source_field: str
    source_date: str
    source_url: str
    fetched_at: str
    status: str
    reason: str = ""

    @property
    def available(self) -> bool:
        return self.price_gbp is not None and self.price_gbp > 0


class OnDemandPriceResolver:
    """Resolve Cardmarket 30-day averages without overwhelming the provider.

    Successful card responses are durable for 24 hours. Temporary failures
    are checkpointed with a retry-after time, and a circuit breaker defers the
    rest of a run when the upstream API is unhealthy. No stale or workbook
    price is ever substituted for the required rolling 30-day field.
    """

    def __init__(
        self,
        root: Path,
        logger: Any | None = None,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.root = Path(root)
        self.logger = logger
        self.session = session or requests.Session()
        self.sleep = sleep
        self.api_root = os.getenv(
            "POKEMON_TCG_API_URL",
            "https://api.pokemontcg.io/v2/cards",
        ).rstrip("/")
        self.fx_api_url = os.getenv(
            "MARKET_FX_API_URL",
            "https://api.frankfurter.dev/v1/latest?base=EUR&symbols=GBP,USD",
        )
        self.timeout_seconds = int(
            os.getenv("ON_DEMAND_PRICE_TIMEOUT_SECONDS", "30")
        )
        self.retry_attempts = max(
            1,
            int(os.getenv("ON_DEMAND_PRICE_RETRY_ATTEMPTS", "3")),
        )
        self.cache_ttl_seconds = max(
            300,
            int(os.getenv("ON_DEMAND_PRICE_CACHE_TTL_SECONDS", "86400")),
        )
        self.failure_cooldown_seconds = max(
            60,
            int(os.getenv("ON_DEMAND_PRICE_FAILURE_COOLDOWN_SECONDS", "60")),
        )
        self.circuit_failure_threshold = max(
            1,
            int(os.getenv("ON_DEMAND_PRICE_CIRCUIT_FAILURES", "5")),
        )
        self.circuit_cooldown_seconds = max(
            60,
            int(os.getenv("ON_DEMAND_PRICE_CIRCUIT_COOLDOWN_SECONDS", "900")),
        )
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "PokemonAuctionScanner-OnDemandPricing/1.0",
            }
        )
        api_key = os.getenv("POKEMON_TCG_API_KEY", "").strip()
        if api_key:
            self.session.headers["X-Api-Key"] = api_key

        self._fx: FxRates | None = None
        self._cards: dict[str, dict[str, Any] | None] = {}
        self._quotes: dict[tuple[str, str], PriceQuote] = {}
        self._closed = False
        cache_path = self.root / "data" / "on-demand-price-cache.sqlite"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(cache_path), timeout=30)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS card_cache (
                card_id TEXT PRIMARY KEY,
                fetched_at REAL NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fetch_failure (
                card_id TEXT PRIMARY KEY,
                failed_at REAL NOT NULL,
                retry_after REAL NOT NULL,
                attempts INTEGER NOT NULL,
                last_error TEXT NOT NULL
            );
            """
        )
        self._db.commit()
        self.api_calls = 0
        self.cache_hits = 0
        self.disk_cache_hits = 0
        self.deferred_requests = 0
        self.network_failures = 0
        self.retry_calls = 0
        self.retry_recoveries = 0
        self.alternate_path_recoveries = 0
        self.available_quotes = 0
        self.unavailable_quotes = 0
        self.quote_requests = 0
        self.expected_quotes: int | None = None
        self._last_progress_at = 0.0
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _log(self, level: str, message: str, *args: Any) -> None:
        if self.logger is not None:
            getattr(self.logger, level)(message, *args)

    def _fx_rates(self) -> FxRates:
        if self._fx is None:
            self._fx = fetch_fx_rates(
                session=self.session,
                api_url=self.fx_api_url,
                timeout_seconds=self.timeout_seconds,
                eur_override=os.getenv("MARKET_EUR_TO_GBP_OVERRIDE", ""),
                usd_override=os.getenv("MARKET_USD_TO_GBP_OVERRIDE", ""),
                previous_rates=None,
            )
            self._log(
                "info",
                "ON-DEMAND FX | 1 EUR = %.6f GBP | %s | %s",
                self._fx.eur_to_gbp,
                self._fx.source,
                self._fx.rate_date,
            )
        return self._fx

    def set_expected_quotes(self, total: int | None) -> None:
        self.expected_quotes = max(0, int(total)) if total is not None else None

    def _fresh_cached_card(self, key: str, now: float) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT fetched_at, payload_json FROM card_cache WHERE card_id = ?",
            (key,),
        ).fetchone()
        if row is None or now - float(row[0]) > self.cache_ttl_seconds:
            return None
        try:
            card = json.loads(str(row[1]))
        except (TypeError, ValueError, json.JSONDecodeError):
            self._db.execute("DELETE FROM card_cache WHERE card_id = ?", (key,))
            self._db.commit()
            return None
        if str(card.get("id", "")).casefold() != key:
            return None
        self.disk_cache_hits += 1
        return card

    def _failure_retry_after(self, key: str) -> float:
        row = self._db.execute(
            "SELECT retry_after FROM fetch_failure WHERE card_id = ?",
            (key,),
        ).fetchone()
        return float(row[0]) if row is not None else 0.0

    def _record_success(self, key: str, card: dict[str, Any], now: float) -> None:
        payload = json.dumps(card, ensure_ascii=False, separators=(",", ":"))
        with self._db:
            self._db.execute(
                "INSERT INTO card_cache(card_id, fetched_at, payload_json) "
                "VALUES(?, ?, ?) ON CONFLICT(card_id) DO UPDATE SET "
                "fetched_at=excluded.fetched_at, payload_json=excluded.payload_json",
                (key, now, payload),
            )
            self._db.execute("DELETE FROM fetch_failure WHERE card_id = ?", (key,))

    def _record_failure(self, key: str, error: str, now: float) -> None:
        row = self._db.execute(
            "SELECT attempts FROM fetch_failure WHERE card_id = ?", (key,)
        ).fetchone()
        attempts = (int(row[0]) if row is not None else 0) + 1
        multiplier = min(8, 2 ** min(max(0, attempts - 1), 3))
        retry_after = now + self.failure_cooldown_seconds * multiplier
        with self._db:
            self._db.execute(
                "INSERT INTO fetch_failure(card_id, failed_at, retry_after, attempts, last_error) "
                "VALUES(?, ?, ?, ?, ?) ON CONFLICT(card_id) DO UPDATE SET "
                "failed_at=excluded.failed_at, retry_after=excluded.retry_after, "
                "attempts=excluded.attempts, last_error=excluded.last_error",
                (key, now, retry_after, attempts, error[:500]),
            )

    def _log_progress(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and self.quote_requests != 1 and self.quote_requests % 25 != 0 and now - self._last_progress_at < 10:
            return
        total = str(self.expected_quotes) if self.expected_quotes is not None else "?"
        self._log(
            "info",
            "PRICE PROGRESS | checked=%s/%s | available=%s | unavailable=%s | "
            "24h-cache hits=%s | API calls=%s | deferred=%s",
            self.quote_requests,
            total,
            self.available_quotes,
            self.unavailable_quotes,
            self.disk_cache_hits,
            self.api_calls,
            self.deferred_requests,
        )
        self._last_progress_at = now

    def _fetch_card(self, card_id: str) -> dict[str, Any] | None:
        key = card_id.casefold()
        if key in self._cards:
            self.cache_hits += 1
            return self._cards[key]

        now = time.time()
        cached = self._fresh_cached_card(key, now)
        if cached is not None:
            self._cards[key] = cached
            return cached

        if now < self._failure_retry_after(key):
            self.deferred_requests += 1
            self._cards[key] = None
            return None

        if now < self._circuit_open_until:
            self.deferred_requests += 1
            self._cards[key] = None
            return None

        direct_url = f"{self.api_root}/{quote(card_id, safe='')}"
        selected_fields = "id,name,set,number,rarity,cardmarket,tcgplayer"
        last_error = ""

        for attempt in range(self.retry_attempts):
            # Repeating an identical request is not sufficient when one API
            # route is unhealthy. Use a progressively broader recovery path:
            # compact single-card, full single-card, then exact-ID collection
            # query. Every successful shape is validated against the card ID.
            if attempt == 0:
                request_path = "single-card compact"
                url = direct_url
                params = {"select": selected_fields}
            elif attempt == 1:
                request_path = "single-card full"
                url = direct_url
                params = None
            else:
                request_path = "exact-ID query"
                url = self.api_root
                params = {
                    "q": f"id:{card_id}",
                    "pageSize": 2,
                    "select": selected_fields,
                }
            try:
                if attempt > 0:
                    self.retry_calls += 1
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout_seconds,
                )
                self.api_calls += 1

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else 2 ** attempt
                    last_error = "Pokemon TCG API rate limit"
                    if attempt + 1 < self.retry_attempts:
                        delay = min(max(wait, 1.0), 30.0)
                        self._log(
                            "info",
                            "PRICE RETRY | card=%s | attempt=%s/%s | "
                            "rate limited; waiting %.1fs",
                            card_id,
                            attempt + 2,
                            self.retry_attempts,
                            delay,
                        )
                        self.sleep(delay)
                        continue

                if response.status_code in {500, 502, 503, 504}:
                    last_error = f"Pokemon TCG API HTTP {response.status_code}"
                    if attempt + 1 < self.retry_attempts:
                        delay = min((2 ** attempt) + random.uniform(0.0, 0.35), 15.0)
                        self._log(
                            "info",
                            "PRICE RETRY | card=%s | attempt=%s/%s | "
                            "HTTP %s; waiting %.1fs",
                            card_id,
                            attempt + 2,
                            self.retry_attempts,
                            response.status_code,
                            delay,
                        )
                        self.sleep(delay)
                        continue

                response.raise_for_status()
                payload = response.json()
                data = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(data, list):
                    matches = [
                        item for item in data
                        if isinstance(item, dict)
                        and str(item.get("id", "")).casefold() == key
                    ]
                    card = matches[0] if len(matches) == 1 else {}
                else:
                    card = data or {}
                if str(card.get("id", "")).casefold() != key:
                    raise RuntimeError("API response card ID did not match")
                self._record_success(key, card, time.time())
                if attempt > 0:
                    self.retry_recoveries += 1
                    self.alternate_path_recoveries += 1
                    self._log(
                        "info",
                        "PRICE RECOVERED | card=%s | succeeded on attempt=%s/%s "
                        "via %s",
                        card_id,
                        attempt + 1,
                        self.retry_attempts,
                        request_path,
                    )
                self._consecutive_failures = 0
                self._cards[key] = card
                return card
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                last_error = str(exc)
                if attempt + 1 < self.retry_attempts:
                    delay = min((2 ** attempt) + random.uniform(0.0, 0.35), 15.0)
                    self._log(
                        "info",
                        "PRICE RETRY | card=%s | attempt=%s/%s | %s; "
                        "waiting %.1fs",
                        card_id,
                        attempt + 2,
                        self.retry_attempts,
                        last_error,
                        delay,
                    )
                    self.sleep(delay)

        now = time.time()
        self.network_failures += 1
        self._consecutive_failures += 1
        self._record_failure(key, last_error or "unknown API error", now)
        if self._consecutive_failures >= self.circuit_failure_threshold:
            self._circuit_open_until = now + self.circuit_cooldown_seconds
            self._log(
                "warning",
                "PRICE API CIRCUIT OPEN | %s consecutive failures; remaining "
                "uncached cards are deferred for %s minutes.",
                self._consecutive_failures,
                max(1, self.circuit_cooldown_seconds // 60),
            )
        self._cards[key] = None
        self._log(
            "warning",
            "ON-DEMAND PRICE UNAVAILABLE | card=%s | all %s attempts failed | %s",
            card_id,
            self.retry_attempts,
            last_error or "unknown API error",
        )
        return None

    @staticmethod
    def _variant_key(value: str) -> str:
        text = " ".join(str(value or "").casefold().replace("-", " ").split())
        aliases = {
            "standard": "normal",
            "unlimited": "normal",
            "unlimited normal": "normal",
            "reverse": "reverse holofoil",
            "reverse holo": "reverse holofoil",
            "holo": "holofoil",
            "1st edition holo": "1st edition holofoil",
        }
        return aliases.get(text, text)

    def _select_record(
        self,
        records: list[PriceVariant],
        requested_variant: str,
    ) -> PriceVariant | None:
        wanted = self._variant_key(requested_variant)
        exact = [
            record
            for record in records
            if self._variant_key(record.variant) == wanted
        ]
        if len(exact) == 1:
            return exact[0]
        return None

    def quote(self, card_id: str, variant: str) -> PriceQuote:
        card_id = str(card_id or "").strip()
        variant = str(variant or "").strip()
        cache_key = (card_id.casefold(), self._variant_key(variant))
        if cache_key in self._quotes:
            self.cache_hits += 1
            return self._quotes[cache_key]

        self.quote_requests += 1

        fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        if not card_id:
            result = PriceQuote(
                card_id="",
                variant=variant,
                price_gbp=None,
                price_eur=None,
                source_field="",
                source_date="",
                source_url="",
                fetched_at=fetched_at,
                status="PRICE UNAVAILABLE",
                reason="Exact Pokemon TCG API card ID is missing",
            )
        else:
            card = self._fetch_card(card_id)
            if card is None:
                result = PriceQuote(
                    card_id=card_id,
                    variant=variant,
                    price_gbp=None,
                    price_eur=None,
                    source_field="",
                    source_date="",
                    source_url="",
                    fetched_at=fetched_at,
                    status="PRICE UNAVAILABLE",
                    reason="Live Pokemon TCG API request failed",
                )
            else:
                record = self._select_record(
                    build_price_variants(card, self._fx_rates()),
                    variant,
                )
                if record is None:
                    result = PriceQuote(
                        card_id=card_id,
                        variant=variant,
                        price_gbp=None,
                        price_eur=None,
                        source_field="",
                        source_date=str(
                            (card.get("cardmarket") or {}).get("updatedAt", "")
                        ),
                        source_url=str(
                            (card.get("cardmarket") or {}).get("url", "")
                        ),
                        fetched_at=fetched_at,
                        status="PRICE UNAVAILABLE",
                        reason="Requested finish/edition is not safely separated",
                    )
                else:
                    result = PriceQuote(
                        card_id=card_id,
                        variant=variant,
                        price_gbp=record.price_gbp,
                        price_eur=record.original_price,
                        source_field=record.source_field,
                        source_date=record.source_date,
                        source_url=record.source_url,
                        fetched_at=fetched_at,
                        status=record.match_status,
                        reason=record.notes,
                    )

        self._quotes[cache_key] = result
        if result.available:
            self.available_quotes += 1
        else:
            self.unavailable_quotes += 1
        self._log_progress(
            force=(
                self.expected_quotes is not None
                and self.quote_requests == self.expected_quotes
            )
        )
        return result

    def apply(self, candidate: Any) -> PriceQuote:
        result = self.quote(candidate.card_id, candidate.variant)
        if result.available:
            candidate.market_value = float(result.price_gbp)
            candidate.source = (
                "Pokemon TCG API / Cardmarket 30-day average (on demand)"
            )
            candidate.source_date = result.source_date
            candidate.source_url = result.source_url
        else:
            candidate.market_value = 0.0
        return result

    def summary(self) -> str:
        return (
            f"Pokemon TCG API calls={self.api_calls}; "
            f"24h-cache hits={self.disk_cache_hits}; "
            f"run-cache hits={self.cache_hits}; "
            f"prices available={self.available_quotes}; "
            f"unavailable={self.unavailable_quotes}; "
            f"deferred={self.deferred_requests}; "
            f"retry calls={self.retry_calls}; "
            f"recovered by retry={self.retry_recoveries}; "
            f"alternate-path recoveries={self.alternate_path_recoveries}; "
            f"final network failures={self.network_failures}"
        )

    def close(self) -> None:
        if not self._closed:
            self._db.close()
            self._closed = True
