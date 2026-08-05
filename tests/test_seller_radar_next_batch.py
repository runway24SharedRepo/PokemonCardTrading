from types import SimpleNamespace

from seller_radar_client import SellerRadarClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def listing(number: int):
    return {
        "itemId": f"v1|{number:012d}|0",
        "title": f"Pokemon card {number}",
    }


def fake_client(pages):
    client = object.__new__(SellerRadarClient)
    client.delay = 0
    client.search_calls = 0
    client.oauth_calls = 0
    client.detail_calls = 0
    client.search_url = "https://example/search"
    client.timeout = 30
    client.delivery_country = "GB"
    client.location_country = "GB"
    client.status = lambda message: None
    client._headers = lambda: {}

    def request(method, url, purpose, **kwargs):
        offset = int(kwargs["params"]["offset"])
        return FakeResponse(
            {
                "total": sum(len(page) for page in pages.values()),
                "itemSummaries": pages.get(offset, []),
            }
        )

    client._request = request
    return client


def test_second_run_skips_first_30_and_selects_next_30(monkeypatch):
    monkeypatch.setenv("SELLER_RADAR_MAX_SEARCH_PAGES", "25")
    page = [listing(number) for number in range(1, 201)]
    client = fake_client({0: page})

    seen = {
        listing(number)["itemId"]
        for number in range(1, 31)
    }
    batch = client.search_next_unseen_inventory(
        seller="seller",
        requested_count=30,
        seen_item_ids=seen,
    )

    assert [value["itemId"] for value in batch.items] == [
        listing(number)["itemId"]
        for number in range(31, 61)
    ]
    assert batch.skipped_previously_scanned == 30
    assert batch.pages_scanned == 1


def test_scanner_moves_to_second_page_when_first_200_seen(
    monkeypatch,
):
    monkeypatch.setenv("SELLER_RADAR_MAX_SEARCH_PAGES", "25")
    pages = {
        0: [listing(number) for number in range(1, 201)],
        200: [
            listing(number)
            for number in range(201, 301)
        ],
    }
    client = fake_client(pages)
    seen = {
        listing(number)["itemId"]
        for number in range(1, 201)
    }

    batch = client.search_next_unseen_inventory(
        seller="seller",
        requested_count=30,
        seen_item_ids=seen,
    )

    assert [value["itemId"] for value in batch.items] == [
        listing(number)["itemId"]
        for number in range(201, 231)
    ]
    assert batch.pages_scanned == 2
    assert batch.skipped_previously_scanned == 200


def test_all_current_inventory_seen_returns_empty_and_exhausted(
    monkeypatch,
):
    monkeypatch.setenv("SELLER_RADAR_MAX_SEARCH_PAGES", "25")
    page = [listing(number) for number in range(1, 51)]
    client = fake_client({0: page})
    seen = {value["itemId"] for value in page}

    batch = client.search_next_unseen_inventory(
        seller="seller",
        requested_count=30,
        seen_item_ids=seen,
    )

    assert batch.items == []
    assert batch.inventory_exhausted
    assert batch.skipped_previously_scanned == 50
