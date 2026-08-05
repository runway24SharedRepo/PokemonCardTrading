from pathlib import Path

from seller_radar_history import SellerRadarHistory


def item(number: int):
    return {
        "itemId": f"v1|{number:012d}|0",
        "title": f"Pokemon listing {number}",
    }


def test_history_round_trip_and_case_insensitive(tmp_path: Path):
    path = tmp_path / "history.json"
    history = SellerRadarHistory(path)
    history.record_batch(
        "SellerABC",
        [item(1), item(2)],
        {
            item(1)["itemId"]: {
                "matched": True,
                "decision": "GREEN",
                "listing_type": "AUCTION",
            },
            item(2)["itemId"]: {
                "matched": False,
                "reason": "No match",
                "listing_type": "BUY IT NOW",
            },
        },
        {
            "run_id": "RUN-1",
            "batch_number": 1,
        },
    )
    history.save()

    loaded = SellerRadarHistory(path)
    assert loaded.scanned_count("sellerabc") == 2
    assert loaded.seen_item_ids("SELLERABC") == {
        item(1)["itemId"],
        item(2)["itemId"],
    }
    assert loaded.completed_run_count("SellerABC") == 1


def test_reset_one_seller(tmp_path: Path):
    path = tmp_path / "history.json"
    history = SellerRadarHistory(path)
    history.record_batch(
        "SellerOne",
        [item(1)],
        {},
        {"run_id": "ONE"},
    )
    history.record_batch(
        "SellerTwo",
        [item(2)],
        {},
        {"run_id": "TWO"},
    )
    history.save()

    removed = history.reset_seller(
        "sellerone",
        backup=False,
    )
    history.save()

    assert removed == 1
    assert history.scanned_count("SellerOne") == 0
    assert history.scanned_count("SellerTwo") == 1
