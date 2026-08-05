from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


class SellerRadarClient:
    """Fresh, paginated eBay Browse searches for one named seller."""

    def __init__(
        self,
        config: dict[str, Any],
        status: Callable[[str], None],
    ) -> None:
        self.client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv(
            "EBAY_CLIENT_SECRET",
            "",
        ).strip()
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "EBAY_CLIENT_ID or EBAY_CLIENT_SECRET is missing from .env."
            )

        self.token_url = config["ebay_token_url"]
        self.search_url = config["ebay_search_url"]
        self.item_url_template = config.get(
            "ebay_item_url_template",
            "https://api.ebay.com/buy/browse/v1/item/{item_id}",
        )
        self.marketplace = os.getenv(
            "EBAY_MARKETPLACE_ID",
            config["marketplace_id"],
        ).strip()
        self.delivery_country = os.getenv(
            "EBAY_DELIVERY_COUNTRY",
            config["delivery_country"],
        ).strip()
        # The Random Sniper configuration uses item_location_country.
        # Accept the older location_country key as a compatibility fallback.
        configured_location_country = (
            config.get("item_location_country")
            or config.get("location_country")
            or "GB"
        )
        self.location_country = os.getenv(
            "EBAY_ITEM_LOCATION_COUNTRY",
            configured_location_country,
        ).strip() or "GB"
        self.retry_attempts = int(config["retry_attempts"])
        self.timeout = int(config["request_timeout_seconds"])
        self.delay = float(config["request_delay_seconds"])
        self.status = status
        self.session = requests.Session()
        self._token = ""
        self._token_expires_at = 0.0

        self.oauth_calls = 0
        self.search_calls = 0
        self.detail_calls = 0

    @property
    def total_api_calls(self) -> int:
        return self.oauth_calls + self.search_calls + self.detail_calls

    def close(self) -> None:
        self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        purpose: str,
        **kwargs,
    ) -> requests.Response:
        last_error: Exception | None = None

        for attempt in range(self.retry_attempts):
            try:
                response = self.session.request(
                    method,
                    url,
                    **kwargs,
                )

                if (
                    400 <= response.status_code < 500
                    and response.status_code != 429
                ):
                    detail = response.text.strip()[:1000]
                    raise RuntimeError(
                        f"eBay returned HTTP {response.status_code} "
                        f"during {purpose}: "
                        f"{detail or '(empty response)'}"
                    )

                if (
                    response.status_code == 429
                    or response.status_code >= 500
                ):
                    raise requests.HTTPError(
                        f"Temporary eBay response "
                        f"{response.status_code}",
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

                wait = min(
                    20.0,
                    2 ** attempt + random.random(),
                )
                self.status(
                    f"eBay request problem during {purpose}; "
                    f"retry {attempt + 2}/{self.retry_attempts} "
                    f"in {wait:.0f}s."
                )
                time.sleep(wait)

        raise RuntimeError(
            f"eBay request failed during {purpose} after "
            f"{self.retry_attempts} attempts: {last_error}"
        )

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        self.oauth_calls += 1
        response = self._request(
            "POST",
            self.token_url,
            purpose="OAuth token",
            auth=HTTPBasicAuth(
                self.client_id,
                self.client_secret,
            ),
            headers={
                "Content-Type":
                "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope":
                    "https://api.ebay.com/oauth/api_scope",
            },
            timeout=self.timeout,
        )
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = (
            time.time()
            + int(payload.get("expires_in", 7200))
        )
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token()}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
        }

    def search_seller_inventory(
        self,
        seller: str,
        requested_count: int,
        query: str = "pokemon",
    ) -> list[dict[str, Any]]:
        """Fetch up to requested_count active auction/fixed-price listings."""

        requested_count = max(1, min(int(requested_count), 1000))
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        offset = 0
        page_number = 0

        while len(output) < requested_count:
            remaining = requested_count - len(output)
            page_size = min(200, remaining)
            page_number += 1

            self.status(
                f"SELLER SEARCH PAGE {page_number} | "
                f"offset={offset} | requesting up to {page_size} listing(s)"
            )

            filters = ",".join(
                [
                    "buyingOptions:{AUCTION|FIXED_PRICE}",
                    f"sellers:{{{seller}}}",
                    f"deliveryCountry:{self.delivery_country}",
                    f"itemLocationCountry:{self.location_country}",
                ]
            )

            time.sleep(self.delay)
            self.search_calls += 1
            response = self._request(
                "GET",
                self.search_url,
                purpose=f"seller inventory page {page_number}",
                headers=self._headers(),
                params={
                    "q": query,
                    "filter": filters,
                    "sort": "endingSoonest",
                    "limit": page_size,
                    "offset": offset,
                },
                timeout=self.timeout,
            )
            items = response.json().get(
                "itemSummaries",
                [],
            )

            added = 0
            for item in items:
                item_id = str(
                    item.get("itemId", "") or ""
                ).strip()
                if not item_id or item_id in seen:
                    continue
                seen.add(item_id)
                output.append(item)
                added += 1
                if len(output) >= requested_count:
                    break

            self.status(
                f"Page {page_number}: eBay returned {len(items)}; "
                f"{added} new; {len(output)} accumulated."
            )

            if len(items) < page_size or added == 0:
                break

            offset += page_size

        return output

    def get_item_details(
        self,
        item_id: str,
    ) -> dict[str, Any]:
        self.detail_calls += 1
        time.sleep(self.delay)
        response = self._request(
            "GET",
            self.item_url_template.format(
                item_id=quote(str(item_id), safe=""),
            ),
            purpose=f"condition details {item_id}",
            headers=self._headers(),
            timeout=self.timeout,
        )
        return response.json()
