from __future__ import annotations
import base64, os, random, time
from datetime import datetime, timezone
from typing import Any
import requests
from .cache import SearchCache

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

class EbayClient:
    def __init__(self, cache: SearchCache | None = None, retry_attempts: int = 4,
                 delay_seconds: float = 0.15) -> None:
        self.client_id = os.environ["EBAY_CLIENT_ID"]
        self.client_secret = os.environ["EBAY_CLIENT_SECRET"]
        self.marketplace = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_GB")
        self.delivery_country = os.getenv("EBAY_DELIVERY_COUNTRY", "GB")
        self.location_country = os.getenv("EBAY_ITEM_LOCATION_COUNTRY", "GB")
        self.retry_attempts = retry_attempts
        self.delay_seconds = delay_seconds
        self.cache = cache
        self._token = ""
        self._token_expires = 0.0
        self.session = requests.Session()

    def _request(self, method: str, url: str, **kwargs):
        last = None
        for attempt in range(self.retry_attempts):
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.HTTPError(f"Temporary eBay response {response.status_code}", response=response)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last = exc
                if attempt + 1 >= self.retry_attempts:
                    break
                time.sleep((2 ** attempt) + random.random())
        raise RuntimeError(f"eBay request failed after {self.retry_attempts} attempts: {last}")

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        raw = f"{self.client_id}:{self.client_secret}".encode()
        auth = base64.b64encode(raw).decode("ascii")
        response = self._request("POST", TOKEN_URL,
            headers={"Authorization": f"Basic {auth}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type":"client_credentials",
                  "scope":"https://api.ebay.com/oauth/api_scope"}, timeout=30)
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires = time.time() + int(payload.get("expires_in", 7200))
        return self._token

    def search_auctions(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        key = f"{self.marketplace}|{self.delivery_country}|{self.location_country}|{limit}|{query}"
        if self.cache:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        filters = ["buyingOptions:{AUCTION}", f"deliveryCountry:{self.delivery_country}",
                   f"itemLocationCountry:{self.location_country}"]
        time.sleep(self.delay_seconds)
        response = self._request("GET", SEARCH_URL,
            headers={"Authorization": f"Bearer {self._access_token()}",
                     "X-EBAY-C-MARKETPLACE-ID": self.marketplace},
            params={"q":query,"filter":",".join(filters),"sort":"endingSoonest",
                    "limit":min(max(limit,1),200)}, timeout=45)
        items = response.json().get("itemSummaries", [])
        if self.cache:
            self.cache.put(key, items)
        return items

def parse_end_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z","+00:00"))
