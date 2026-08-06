from long_term_investment import LONG_TERM_HEADERS
from seller_radar_excel import SellerRadarExcelAdapter


def test_long_term_block_has_fifteen_columns():
    assert len(LONG_TERM_HEADERS) == 15
    assert LONG_TERM_HEADERS[0] == "Long-Term Score"
    assert LONG_TERM_HEADERS[-1] == "Investment Risks"


def test_seller_headers_place_long_term_block_after_pricecharting():
    headers = SellerRadarExcelAdapter._headers()
    price_index = headers.index("PriceCharting")
    assert headers[price_index + 1: price_index + 16] == LONG_TERM_HEADERS
    assert headers[price_index + 16] == "Target Delivered (£)"
    assert len(headers) == 65
