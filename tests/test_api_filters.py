from datetime import datetime, timezone

from live_radar.ebay_client import EbayBrowseClient


def test_utc_filter_format():
    value = EbayBrowseClient._utc(
        datetime(
            2026,
            8,
            4,
            18,
            30,
            tzinfo=timezone.utc,
        )
    )
    assert value == "2026-08-04T18:30:00.000Z"
