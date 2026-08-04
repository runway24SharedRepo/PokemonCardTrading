from __future__ import annotations

import json
import os
import random
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth


class SearchCache:
    def __init__(self, path: Path, ttl_minutes: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.ttl = timedelta(minutes=ttl_minutes)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS random_search_cache(
                cache_key TEXT PRIMARY KEY,
                stored_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def get(self, key: str) -> list[dict[str, Any]] | None:
        row = self.connection.execute(
            """
            SELECT stored_at, payload
            FROM random_search_cache
            WHERE cache_key = ?
            """,
            (key,),
        ).fetchone()
        if not row:
            return None
        stored_at = datetime.fromisoformat(row[0])
        if datetime.now(timezone.utc) - stored_at > self.ttl:
            self.connection.execute(
                "DELETE FROM random_search_cache WHERE cache_key = ?",
                (key,),
            )
            self.connection.commit()
            return None
        return json.loads(row[1])

    def put(self, key: str, payload: list[dict[str, Any]]) -> None:
        self.connection.execute(
            """
            INSERT INTO random_search_cache(cache_key, stored_at, payload)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                stored_at = excluded.stored_at,
                payload = excluded.payload
            """,
            (
                key,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


class EbayBrowseClient:
    def __init__(
        self,
        config: dict[str, Any],
        cache_path: Path,
    ) -> None:
        self.client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET", "").strip()
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "EBAY_CLIENT_ID or EBAY_CLIENT_SECRET is missing from .env."
            )

        self.token_url = config["ebay_token_url"]
        self.search_url = config["ebay_search_url"]
        self.marketplace = os.getenv(
            "EBAY_MARKETPLACE_ID",
            config["marketplace_id"],
        ).strip()
        self.delivery_country = os.getenv(
            "EBAY_DELIVERY_COUNTRY",
            config["delivery_country"],
        ).strip()
        self.location_country = os.getenv(
            "EBAY_ITEM_LOCATION_COUNTRY",
            config["item_location_country"],
        ).strip()
        self.results_per_query = int(config["results_per_query"])
        self.retry_attempts = int(config["retry_attempts"])
        self.timeout = int(config["request_timeout_seconds"])
        self.delay = float(config["request_delay_seconds"])
        self.session = requests.Session()
        self.cache = SearchCache(
            cache_path,
            int(config["search_cache_minutes"]),
        )
        self._token = ""
        self._token_expires_at = 0.0

    def close(self) -> None:
        self.cache.close()

    def _request(self, method: str, url: str, **kwargs):
        last_error: Exception | None = None

        for attempt in range(self.retry_attempts):
            try:
                response = self.session.request(method, url, **kwargs)

                if 400 <= response.status_code < 500 and response.status_code != 429:
                    detail = response.text.strip()[:1000]
                    raise RuntimeError(
                        f"eBay returned HTTP {response.status_code}: "
                        f"{detail or '(empty response)'}"
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.HTTPError(
                        f"Temporary eBay response {response.status_code}",
                        response=response,
                    )

                response.raise_for_status()
                return response
            except RuntimeError:
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 >= self.retry_attempts:
                    break
                time.sleep(min(30.0, 2 ** attempt + random.random()))

        raise RuntimeError(
            f"eBay request failed after {self.retry_attempts} attempts: "
            f"{last_error}"
        )

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        response = self._request(
            "POST",
            self.token_url,
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=self.timeout,
        )
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = (
            time.time() + int(payload.get("expires_in", 7200))
        )
        return self._token

    def test_connection(self) -> dict[str, Any]:
        token = self._access_token()
        return {
            "ok": True,
            "marketplace": self.marketplace,
            "token_length": len(token),
        }

    def search_listings(
        self,
        query: str,
        listing_formats: str = "Auctions + Buy It Now",
    ) -> list[dict[str, Any]]:
        mode = str(listing_formats or "Auctions + Buy It Now").strip()
        if mode == "Auctions only":
            buying_filter = "buyingOptions:{AUCTION}"
        elif mode == "Buy It Now only":
            buying_filter = "buyingOptions:{FIXED_PRICE}"
        else:
            buying_filter = "buyingOptions:{AUCTION|FIXED_PRICE}"

        cache_key = (
            f"phase4.2|{self.marketplace}|{self.delivery_country}|"
            f"{self.location_country}|{self.results_per_query}|"
            f"{buying_filter}|{query}"
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        time.sleep(self.delay)
        response = self._request(
            "GET",
            self.search_url,
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            },
            params={
                "q": query,
                "filter": ",".join(
                    [
                        buying_filter,
                        f"deliveryCountry:{self.delivery_country}",
                        f"itemLocationCountry:{self.location_country}",
                    ]
                ),
                "sort": "endingSoonest",
                "limit": min(max(self.results_per_query, 1), 200),
            },
            timeout=self.timeout,
        )
        items = response.json().get("itemSummaries", [])
        self.cache.put(cache_key, items)
        return items

    def search_auctions(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        """Compatibility wrapper retained for older integrations."""
        return self.search_listings(query, "Auctions only")

