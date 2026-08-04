from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import ebay_watchlist
from ebay_watchlist import WatchlistCallResult, sync_green_results


class FakeClient:
    configured = True
    authentication_mode = "fake"
    batch_size = 25

    def __init__(self, logger=None):
        pass

    def add_item_ids(self, item_ids):
        values = list(item_ids)
        return [
            (
                values,
                WatchlistCallResult(
                    acknowledgement="Success",
                    watchlist_count=len(values),
                    watchlist_maximum=400,
                ),
            )
        ]

    def close(self):
        pass


def test_green_result_is_confirmed(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("EBAY_WATCHLIST_ENABLED", "YES")
    monkeypatch.setenv("EBAY_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(
        ebay_watchlist,
        "EbayWatchlistClient",
        FakeClient,
    )

    listing = SimpleNamespace(
        item_id="v1|123456789012|0",
        decision="GREEN",
        title="Pikachu 58/102",
        notes="",
        end_time=(
            datetime.now(timezone.utc)
            + timedelta(hours=1)
        ),
    )
    logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )

    summary = sync_green_results(
        [listing],
        root=tmp_path,
        source="TEST",
        logger=logger,
    )
    assert summary.confirmed == 1
    assert "added/confirmed" in listing.notes
    assert (
        tmp_path
        / "data"
        / "ebay-watchlist-managed.json"
    ).exists()


def test_multi_variation_is_skipped(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("EBAY_WATCHLIST_ENABLED", "YES")
    monkeypatch.setenv("EBAY_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(
        ebay_watchlist,
        "EbayWatchlistClient",
        FakeClient,
    )

    listing = SimpleNamespace(
        item_id="v1|123456789012|987",
        decision="GREEN",
        title="Choose a card",
        notes="",
        end_time=(
            datetime.now(timezone.utc)
            + timedelta(hours=1)
        ),
    )
    logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )

    summary = sync_green_results(
        [listing],
        root=tmp_path,
        source="TEST",
        logger=logger,
    )
    assert summary.confirmed == 0
    assert summary.skipped_variations == 1
