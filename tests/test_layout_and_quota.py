from datetime import datetime, timezone

from check_ebay_api_limits import collect_rates


def test_collect_browse_daily_rate():
    payload = {
        "rateLimits": [
            {
                "apiContext": "buy",
                "apiName": "browse",
                "apiVersion": "v1",
                "resources": [
                    {
                        "name": "buy.browse",
                        "rates": [
                            {
                                "limit": 5000,
                                "count": 123,
                                "remaining": 4877,
                                "reset": "2026-08-05T07:00:00.000Z",
                                "timeWindow": 86400,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    rates = collect_rates(payload)
    assert len(rates) == 1
    assert rates[0]["used"] == 123
    assert rates[0]["remaining"] == 4877
    assert rates[0]["window"] == 86400
