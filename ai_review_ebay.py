from __future__ import annotations

import os
import random
import time
from typing import Any
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth

from ai_review_cache import AIReviewCache


class AIReviewEbayClient:
    def __init__(self, config: dict[str, Any], cache: AIReviewCache) -> None:
        self.client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET", "").strip()
        if not self.client_id or not self.client_secret:
            raise RuntimeError("eBay credentials are unavailable.")
        self.token_url = config["ebay_token_url"]
        self.item_url_template = config.get(
            "ebay_item_url_template",
            "https://api.ebay.com/buy/browse/v1/item/{item_id}",
        )
        self.marketplace = os.getenv(
            "EBAY_MARKETPLACE_ID", config.get("marketplace_id", "EBAY_GB")
        ).strip()
        self.timeout = int(config.get("request_timeout_seconds", 30))
        self.retry_attempts = int(config.get("retry_attempts", 3))
        self.delay = float(config.get("request_delay_seconds", 0.15))
        self.cache = cache
        self.session = requests.Session()
        self._token = ""
        self._token_expires = 0.0

    def close(self) -> None:
        self.session.close()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.retry_attempts):
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.HTTPError("Temporary eBay response", response=response)
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"eBay HTTP {response.status_code}: {response.text[:500]}"
                    )
                return response
            except RuntimeError:
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 >= self.retry_attempts:
                    break
                time.sleep(min(10, 2**attempt + random.random()))
        raise RuntimeError(f"eBay detail request failed: {last_error}")

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        response = self._request(
            "POST",
            self.token_url,
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=self.timeout,
        )
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires = time.time() + int(payload.get("expires_in", 7200))
        return self._token

    def get_item_details(self, item_id: str) -> dict[str, Any]:
        cached = self.cache.get_ebay_details(item_id)
        if cached is not None:
            return cached
        time.sleep(self.delay)
        response = self._request(
            "GET",
            self.item_url_template.format(item_id=quote(str(item_id), safe="")),
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            },
            timeout=self.timeout,
        )
        payload = response.json()
        self.cache.put_ebay_details(item_id, payload)
        return payload


def compact_item_details(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    aspects: list[str] = []
    for aspect in payload.get("localizedAspects") or []:
        name = str(aspect.get("name", "") or "").strip()
        value = str(aspect.get("value", "") or "").strip()
        if name and value:
            aspects.append(f"{name}: {value}")
    seller = payload.get("seller") or {}
    return {
        "title": str(payload.get("title", "") or "")[:500],
        "short_description": str(payload.get("shortDescription", "") or "")[:4000],
        "condition": str(payload.get("condition", "") or "")[:200],
        "condition_description": str(payload.get("conditionDescription", "") or "")[:2000],
        "item_specifics": aspects[:30],
        "buying_options": [str(v) for v in (payload.get("buyingOptions") or [])][:10],
        "seller": {
            "username": str(seller.get("username", "") or "")[:200],
            "feedback_percentage": str(seller.get("feedbackPercentage", "") or "")[:50],
            "feedback_score": str(seller.get("feedbackScore", "") or "")[:50],
        },
    }
