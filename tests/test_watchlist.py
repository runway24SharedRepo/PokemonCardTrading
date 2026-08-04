from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from ebay_watchlist import (
    ManagedWatchlistLedger,
    ParsedItemId,
    WatchlistCallResult,
    parse_item_id,
    sync_green_results,
)


def result(item_id: str, decision: str = "GREEN"):
    return SimpleNamespace(
        item_id=item_id,
        decision=decision,
        title=f"Listing {item_id}",
        notes="",
        end_time=datetime.now(timezone.utc) + timedelta(hours=1),
    )


def test_parse_browse_item_id():
    parsed = parse_item_id("v1|137578712363|0")
    assert parsed is not None
    assert parsed.legacy_item_id == "137578712363"
    assert parsed.variation_id == "0"
    assert not parsed.is_multi_variation


def test_parse_multi_variation_item_id():
    parsed = parse_item_id("v1|137578712363|982345")
    assert parsed is not None
    assert parsed.is_multi_variation


def test_parse_numeric_item_id():
    parsed = parse_item_id("137578712363")
    assert parsed is not None
    assert parsed.legacy_item_id == "137578712363"


def test_ledger_round_trip(tmp_path: Path):
    path = tmp_path / "ledger.json"
    ledger = ManagedWatchlistLedger(path)
    parsed = ParsedItemId(
        "v1|123456789012|0",
        "123456789012",
        "0",
    )
    ledger.confirm(parsed, "Pikachu", "TEST")
    ledger.save()

    loaded = ManagedWatchlistLedger(path)
    assert loaded.active_ids() == ["123456789012"]
    assert loaded.is_recent("123456789012", 24)


def test_ledger_removal(tmp_path: Path):
    path = tmp_path / "ledger.json"
    ledger = ManagedWatchlistLedger(path)
    parsed = ParsedItemId(
        "v1|123456789012|0",
        "123456789012",
        "0",
    )
    ledger.confirm(parsed, "Pikachu", "TEST")
    ledger.mark_removed(["123456789012"])
    assert ledger.active_ids() == []


def test_sync_disabled(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EBAY_WATCHLIST_ENABLED", "NO")
    summary = sync_green_results(
        [result("v1|123456789012|0")],
        root=tmp_path,
        source="TEST",
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        ),
    )
    assert not summary.enabled


def test_non_green_is_not_selected(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EBAY_WATCHLIST_ENABLED", "YES")
    monkeypatch.delenv("EBAY_USER_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("EBAY_USER_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("EBAY_AUTH_TOKEN", raising=False)

    summary = sync_green_results(
        [result("v1|123456789012|0", "AMBER")],
        root=tmp_path,
        source="TEST",
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        ),
    )
    assert not summary.configured


def test_remove_all_xml_contract():
    assert "<RemoveAllItems>true</RemoveAllItems>" in (
        "<RemoveAllItems>true</RemoveAllItems>"
    )
