from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload"


class NoScannerWatchlistWritesTests(unittest.TestCase):
    def _source(self, filename: str) -> str:
        return (PAYLOAD / filename).read_text(encoding="utf-8")

    def test_live_scanner_has_no_watchlist_write_path(self) -> None:
        source = self._source("live_opportunity_radar.py")
        ast.parse(source)
        self.assertNotIn("ebay_watchlist", source)
        self.assertNotIn("sync_green_results", source)
        self.assertNotIn("AddToWatchList", source)
        self.assertNotIn("eBay Watchlist:", source)

    def test_random_sniper_has_no_watchlist_write_path(self) -> None:
        source = self._source("random_range_sniper.py")
        ast.parse(source)
        self.assertNotIn("ebay_watchlist", source)
        self.assertNotIn("sync_green_results", source)
        self.assertNotIn("AddToWatchList", source)
        self.assertNotIn("eBay Watchlist:", source)

    def test_scanning_and_workbook_outputs_remain_present(self) -> None:
        live = self._source("live_opportunity_radar.py")
        random = self._source("random_range_sniper.py")
        self.assertIn("excel.write_results(final_results)", live)
        self.assertIn("excel.update_dashboard(final_results)", live)
        self.assertIn("excel.write_results(all_results)", random)
        self.assertIn("excel.write_random_snipe_queue(random_queue)", random)
        self.assertIn("excel.copy_green_to_snipe_queue(random_queue)", random)


if __name__ == "__main__":
    unittest.main(verbosity=2)
