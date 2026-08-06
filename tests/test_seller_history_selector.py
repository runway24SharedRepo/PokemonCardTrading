from pathlib import Path

import pytest

from manage_seller_radar_history import parse_selection
from seller_radar_history import SellerRadarHistory


def item(number: int):
    return {
        "itemId": f"v1|{number:012d}|0",
        "title": f"Pokemon listing {number}",
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("3;4", [3, 4]),
        ("1,3", [1, 3]),
        ("1 3", [1, 3]),
        ("2-4", [2, 3, 4]),
        ("4-2", [2, 3, 4]),
        ("1;1;2", [1, 2]),
        ("A", [1, 2, 3, 4]),
        ("all", [1, 2, 3, 4]),
        ("Q", []),
    ],
)
def test_parse_selection(value, expected):
    assert parse_selection(value, 4) == expected


@pytest.mark.parametrize(
    "value",
    ["", "0", "5", "abc", "1;x"],
)
def test_invalid_selection(value):
    with pytest.raises(ValueError):
        parse_selection(value, 4)


def test_tracked_sellers_are_alphabetical(tmp_path: Path):
    history = SellerRadarHistory(tmp_path / "history.json")
    history.record_batch(
        "lotto",
        [item(1)],
        {},
        {"run_id": "LOTTO"},
    )
    history.record_batch(
        "Antonio",
        [item(2), item(3)],
        {},
        {"run_id": "ANTONIO"},
    )
    history.record_batch(
        "fabien",
        [item(4)],
        {},
        {"run_id": "FABIEN"},
    )

    tracked = history.tracked_sellers()
    assert [entry["seller"] for entry in tracked] == [
        "Antonio",
        "fabien",
        "lotto",
    ]
    assert tracked[0]["scanned_count"] == 2


def test_multi_reset_preserves_unselected_seller(tmp_path: Path):
    path = tmp_path / "history.json"
    history = SellerRadarHistory(path)

    for index, seller in enumerate(
        ["antonio", "alex", "fabien", "lotto"],
        start=1,
    ):
        history.record_batch(
            seller,
            [item(index)],
            {},
            {"run_id": seller.upper()},
        )
    history.save()

    removed, backup = history.reset_sellers(
        ["fabien", "lotto"],
        backup=True,
    )
    history.save()

    assert removed == {
        "fabien": 1,
        "lotto": 1,
    }
    assert backup is not None
    assert backup.exists()
    assert history.scanned_count("antonio") == 1
    assert history.scanned_count("alex") == 1
    assert history.scanned_count("fabien") == 0
    assert history.scanned_count("lotto") == 0
