from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth


class ApiBudget:
    def __init__(self, maximum_calls: int) -> None:
        self.maximum_calls = max(1, int(maximum_calls))
        self.used = 0

    @property
    def remaining(self) -> int:
        return max(0, self.maximum_calls - self.used)

    def consume(self, purpose: str) -> None:
        if self.used >= self.maximum_calls:
            raise RuntimeError(
                "Editable Maximum total API calls limit reached "
                f"before {purpose}."
            )
        self.used += 1


class EbayBrowseClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        config: dict[str, Any],
        budget: ApiBudget,
        status,
    ) -> None:
        if not client_id or not client_secret:
            raise RuntimeError(
                "EBAY_CLIENT_ID or EBAY_CLIENT_SECRET is missing from .env."
            )

        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = config["ebay_token_url"]
        self.search_url = config["ebay_search_url"]
        self.item_url_template = config["ebay_item_url_template"]
        self.marketplace = config["marketplace_id"]
        self.delivery_country = config["delivery_country"]
        self.location_country = config["item_location_country"]
        self.timeout = int(config["request_timeout_seconds"])
        self.retry_attempts = int(config["retry_attempts"])
        self.delay = float(config["request_delay_seconds"])
        self.budget = budget
        self.status = status
        self.session = requests.Session()
        self._token = ""
        self._token_expires = 0.0

    @staticmethod
    def _utc(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        purpose: str,
        **kwargs,
    ) -> requests.Response:
        self.budget.consume(purpose)
        last_error: Exception | None = None

        for attempt in range(self.retry_attempts):
            try:
                response = self.session.request(
                    method,
                    url,
                    **kwargs,
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

                if response.status_code >= 400:
                    detail = response.text.strip()[:1000]
                    raise RuntimeError(
                        f"eBay returned HTTP "
                        f"{response.status_code}: "
                        f"{detail or '(empty response)'}"
                    )

                return response
            except RuntimeError:
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 >= self.retry_attempts:
                    break

                wait = min(20.0, 2 ** attempt + random.random())
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
        if self._token and time.time() < self._token_expires - 60:
            return self._token

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
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=self.timeout,
        )
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires = (
            time.time() + int(payload.get("expires_in", 7200))
        )
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token()}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
        }

    def broad_auction_page(
        self,
        query: str,
        minimum_minutes: int,
        maximum_hours: float,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        start = now + timedelta(minutes=minimum_minutes)
        end = now + timedelta(hours=maximum_hours)

        filters = [
            "buyingOptions:{AUCTION}",
            f"deliveryCountry:{self.delivery_country}",
            f"itemLocationCountry:{self.location_country}",
            (
                "itemEndDate:["
                f"{self._utc(start)}..{self._utc(end)}]"
            ),
        ]

        time.sleep(self.delay)
        response = self._request(
            "GET",
            self.search_url,
            purpose=f"broad radar offset {offset}",
            headers=self._headers(),
            params={
                "q": query,
                "filter": ",".join(filters),
                "sort": "endingSoonest",
                "limit": min(max(int(limit), 1), 200),
                "offset": max(0, int(offset)),
            },
            timeout=self.timeout,
        )
        return response.json().get("itemSummaries", [])

    def seller_auction_page(
        self,
        seller: str,
        query: str,
        minimum_minutes: int,
        maximum_hours: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        start = now + timedelta(minutes=minimum_minutes)
        end = now + timedelta(hours=maximum_hours)

        filters = [
            "buyingOptions:{AUCTION}",
            f"sellers:{{{seller}}}",
            f"deliveryCountry:{self.delivery_country}",
            f"itemLocationCountry:{self.location_country}",
            (
                "itemEndDate:["
                f"{self._utc(start)}..{self._utc(end)}]"
            ),
        ]

        time.sleep(self.delay)
        response = self._request(
            "GET",
            self.search_url,
            purpose=f"seller expansion {seller}",
            headers=self._headers(),
            params={
                "q": query,
                "filter": ",".join(filters),
                "sort": "endingSoonest",
                "limit": min(max(int(limit), 1), 200),
                "offset": 0,
            },
            timeout=self.timeout,
        )
        return response.json().get("itemSummaries", [])

    def get_item_details(
        self,
        item_id: str,
    ) -> dict[str, Any]:
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
