from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth


TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
RATE_LIMIT_URL = (
    "https://api.ebay.com/developer/analytics/"
    "v1_beta/rate_limit/"
)
SCOPE = "https://api.ebay.com/oauth/api_scope"


def local_time(value: str) -> str:
    if not value:
        return "Not supplied"
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        return parsed.astimezone().strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        )
    except ValueError:
        return value


def get_token(
    client_id: str,
    client_secret: str,
) -> str:
    response = requests.post(
        TOKEN_URL,
        auth=HTTPBasicAuth(client_id, client_secret),
        headers={
            "Content-Type":
            "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "client_credentials",
            "scope": SCOPE,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            "OAuth token request failed: "
            f"HTTP {response.status_code} "
            f"{response.text[:700]}"
        )
    return response.json()["access_token"]


def get_limits(token: str) -> dict[str, Any]:
    response = requests.get(
        RATE_LIMIT_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        params={
            "api_context": "buy",
            "api_name": "browse",
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            "Developer Analytics request failed: "
            f"HTTP {response.status_code} "
            f"{response.text[:1000]}"
        )
    return response.json()


def collect_rates(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for api in payload.get("rateLimits") or []:
        context = str(api.get("apiContext", "") or "")
        name = str(api.get("apiName", "") or "")
        version = str(api.get("apiVersion", "") or "")

        if context.casefold() != "buy":
            continue
        if name.casefold() != "browse":
            continue

        for resource in api.get("resources") or []:
            resource_name = str(
                resource.get("name", "") or "Browse API"
            )
            for rate in resource.get("rates") or []:
                limit = int(rate.get("limit") or 0)
                remaining = int(rate.get("remaining") or 0)
                count_value = rate.get("count")
                used = (
                    int(count_value)
                    if count_value is not None
                    else max(0, limit - remaining)
                )
                output.append(
                    {
                        "context": context,
                        "api": name,
                        "version": version,
                        "resource": resource_name,
                        "limit": limit,
                        "used": used,
                        "remaining": remaining,
                        "reset": str(rate.get("reset", "") or ""),
                        "window": int(rate.get("timeWindow") or 0),
                    }
                )

    return output


def main() -> int:
    root = Path(__file__).resolve().parent
    load_dotenv(
        root / ".env",
        override=True,
        encoding="utf-8-sig",
    )

    client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
    client_secret = os.getenv(
        "EBAY_CLIENT_SECRET",
        "",
    ).strip()

    if not client_id or not client_secret:
        print(
            "ERROR: EBAY_CLIENT_ID or EBAY_CLIENT_SECRET "
            "is missing from .env."
        )
        return 1

    print("Requesting an eBay application token...")
    token = get_token(client_id, client_secret)

    print("Reading Buy Browse API rate limits...")
    payload = get_limits(token)
    rates = collect_rates(payload)

    if not rates:
        print()
        print(
            "No Buy/Browse rate-limit records were returned "
            "for this production keyset."
        )
        print(
            "The response has been saved to "
            "ebay-api-limits-raw.json for inspection."
        )
        import json
        (root / "ebay-api-limits-raw.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        return 2

    daily = [
        rate for rate in rates
        if rate["window"] == 86400
    ]
    short_window = [
        rate for rate in rates
        if rate["window"] != 86400
    ]

    print()
    print("=" * 72)
    print("EBAY BUY / BROWSE API QUOTA")
    print("=" * 72)

    displayed = daily or rates
    for rate in displayed:
        window_label = (
            "24 hours"
            if rate["window"] == 86400
            else f"{rate['window']} seconds"
        )
        print()
        print(f"Resource : {rate['resource']}")
        print(f"Window   : {window_label}")
        print(f"Limit    : {rate['limit']:,}")
        print(f"Used     : {rate['used']:,}")
        print(f"Remaining: {rate['remaining']:,}")
        print(f"Resets   : {local_time(rate['reset'])}")

    if daily:
        lowest = min(
            daily,
            key=lambda rate: rate["remaining"],
        )
        percentage = (
            lowest["remaining"] / lowest["limit"] * 100
            if lowest["limit"]
            else 0
        )
        print()
        print("-" * 72)
        print(
            "CONSERVATIVE DAILY REMAINING FIGURE: "
            f"{lowest['remaining']:,} calls "
            f"({percentage:.1f}% remaining)"
        )
        print(
            "This is the lowest remaining daily Browse quota "
            "reported across Browse resources."
        )

    if short_window:
        print()
        print("Additional short-window limits:")
        for rate in short_window:
            print(
                f"  {rate['resource']}: "
                f"{rate['remaining']:,}/{rate['limit']:,} remaining; "
                f"resets {local_time(rate['reset'])}"
            )

    print()
    print(
        "This checker uses the Identity and Developer Analytics APIs. "
        "It does not perform a Browse search."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print()
        print(f"ERROR: {exc}")
        raise SystemExit(1)
