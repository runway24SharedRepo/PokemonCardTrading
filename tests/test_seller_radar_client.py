from seller_radar_client import SellerRadarClient


def test_client_tracks_total_calls_without_initial_calls():
    client = object.__new__(SellerRadarClient)
    client.oauth_calls = 1
    client.search_calls = 2
    client.detail_calls = 3
    assert client.total_api_calls == 6
