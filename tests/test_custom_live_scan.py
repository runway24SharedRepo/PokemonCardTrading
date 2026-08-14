from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload"
sys.path.insert(0, str(PAYLOAD))

from custom_input import parse_market_data_references


class CustomLiveScanTests(unittest.TestCase):
    def test_sheet_lookup_uses_normalised_enumeration_not_com_string_lookup(self) -> None:
        source = (PAYLOAD / "random_sniper" / "excel_adapter.py").read_text(
            encoding="utf-8"
        )
        ast.parse(source)
        self.assertIn("def _normalise_sheet_name", source)
        self.assertIn("for index in range(1, int(self.book.Worksheets.Count) + 1)", source)
        self.assertNotIn("return self.book.Worksheets(name)", source)
        self.assertIn('self.sheet("Custom Live Results")', source)
        self.assertIn('self.sheet("Custom Live Queue")', source)
        self.assertIn("template.Copy(None, last_sheet)", source)
        self.assertIn("self.book.Worksheets.Add(None, last_sheet, 1)", source)
        self.assertIn("template.UsedRange.Copy(created.Cells(1, 1))", source)

    def test_input_accepts_h_references_comments_and_deduplicates(self) -> None:
        self.assertEqual(
            parse_market_data_references(
                "\ufeff# selected cards\nH1810\n$H$1811 # Pikachu\nh1810\n"
            ),
            [("H1810", 1810), ("H1811", 1811)],
        )

    def test_input_rejects_non_h_columns_and_headers(self) -> None:
        with self.assertRaisesRegex(ValueError, "column-H reference"):
            parse_market_data_references("G1811")
        with self.assertRaisesRegex(ValueError, "header row"):
            parse_market_data_references("H4")

    def test_custom_runtime_is_manual_h_priced_and_watchlist_read_only(self) -> None:
        source = (PAYLOAD / "live_scan_custom.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("read_custom_candidates", source)
        self.assertNotIn("OnDemandPriceResolver", source)
        self.assertNotIn("sync_green_results", source)
        self.assertNotIn("AddToWatchList", source)
        self.assertIn('print("eBay Watchlist writes: DISABLED")', source)

    def test_existing_random_and_live_scanners_remain_watchlist_read_only(self) -> None:
        for name in ("random_range_sniper.py", "live_opportunity_radar.py"):
            source = (PAYLOAD / name).read_text(encoding="utf-8")
            self.assertNotIn("sync_green_results", source)
            self.assertNotIn("AddToWatchList", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
