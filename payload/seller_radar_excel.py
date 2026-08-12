from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from edition_safety import preferred_result_image
from random_sniper.core import ListingResult
from random_sniper.excel_adapter import ExcelAdapter
from market_links import market_links_for_candidate
from long_term_investment import LONG_TERM_HEADERS, assessment_values


XL_TOP = -4160
XL_LEFT = -4131
XL_CENTER = -4108
XL_UP = -4162


def seller_sheet_name(username: str) -> str:
    clean = re.sub(
        r"[\[\]:*?/\\]+",
        "-",
        str(username or "").strip(),
    )
    clean = re.sub(r"\s+", " ", clean).strip(" .-'")
    clean = clean or "Unknown Seller"

    base = f"Seller - {clean}"
    if len(base) <= 31:
        return base

    digest = hashlib.sha1(
        clean.casefold().encode("utf-8")
    ).hexdigest()[:5]
    return f"Seller - {clean[:16]}-{digest}"[:31]


class SellerRadarExcelAdapter(ExcelAdapter):
    TABLE_HEADER_ROW = 8
    DATA_START_ROW = 9

    def _get_or_add_sheet(self, name: str):
        try:
            return self.book.Worksheets(name), False
        except Exception:
            sheet = self.book.Worksheets.Add(
                After=self.book.Worksheets(
                    self.book.Worksheets.Count
                )
            )
            sheet.Name = name
            return sheet, True

    def _existing_statuses(
        self,
        sheet,
    ) -> dict[str, str]:
        output: dict[str, str] = {}
        last_row = max(
            self.DATA_START_ROW,
            int(
                sheet.Cells(
                    sheet.Rows.Count,
                    14,
                ).End(XL_UP).Row
            ),
        )
        status_column = 63
        try:
            if str(sheet.Cells(8, 63).Value or "") != "Status":
                if str(sheet.Cells(8, 48).Value or "") == "Status":
                    status_column = 48
                else:
                    status_column = 44
        except Exception:
            status_column = 44

        for row in range(
            self.DATA_START_ROW,
            last_row + 1,
        ):
            item_id = str(
                sheet.Cells(row, 14).Value or ""
            ).strip()
            status = str(
                sheet.Cells(row, status_column).Value or ""
            ).strip()
            if item_id and status:
                output[item_id] = status
        return output

    @staticmethod
    def _set_validation(cell_range, values: list[str]) -> None:
        try:
            cell_range.Validation.Delete()
        except Exception:
            pass
        cell_range.Validation.Add(
            Type=3,
            AlertStyle=1,
            Operator=1,
            Formula1=",".join(values),
        )
        cell_range.Validation.IgnoreBlank = True
        cell_range.Validation.InCellDropdown = True

    def _style_title(
        self,
        sheet,
        seller: str,
    ) -> None:
        navy = self._excel_rgb(31, 78, 121)
        pale = self._excel_rgb(221, 235, 247)

        sheet.Range("A1:BM1").Merge()
        sheet.Cells(1, 1).Value = (
            f"Seller Radar — {seller}"
        )
        sheet.Range("A1:BM1").Interior.Color = navy
        sheet.Range("A1:BM1").Font.Color = self._excel_rgb(
            255,
            255,
            255,
        )
        sheet.Range("A1:BM1").Font.Bold = True
        sheet.Range("A1:BM1").Font.Size = 17
        sheet.Range("A1:BM1").VerticalAlignment = XL_CENTER
        sheet.Rows(1).RowHeight = 30

        sheet.Range("A2:BM2").Merge()
        sheet.Cells(2, 1).Value = (
            "Dedicated analysis of this seller's active Pokémon listings. "
            "Exact card matching, separate auction and Buy It Now outcomes, "
            "condition intelligence, market targets and native eBay links."
        )
        sheet.Range("A2:BM2").Interior.Color = pale
        sheet.Range("A2:BM2").WrapText = True
        sheet.Rows(2).RowHeight = 38

    def _write_summary(
        self,
        sheet,
        summary: dict[str, Any],
    ) -> None:
        labels = [
            ("A4", "Seller", "B4", summary["seller"]),
            ("D4", "Last scan", "E4", summary["last_scan"]),
            ("G4", "Requested", "H4", summary["requested"]),
            ("J4", "Listings fetched", "K4", summary["fetched"]),
            ("M4", "Exact matches", "N4", summary["matched"]),
            ("P4", "GREEN", "Q4", summary["green"]),
            ("S4", "AMBER", "T4", summary["amber"]),
            ("A5", "RED", "B5", summary["red"]),
            ("D5", "Unmatched", "E5", summary["unmatched"]),
            ("G5", "Search calls", "H5", summary["search_calls"]),
            ("J5", "Condition checks", "K5", summary["detail_calls"]),
            ("M5", "Total API calls", "N5", summary["total_calls"]),
            ("P5", "Target ratio", "Q5", summary["target_ratio"]),
            ("S5", "Watchlist", "T5", summary["watchlist"]),
            ("A6", "Batch number", "B6", summary["batch_number"]),
            (
                "D6",
                "Previously scanned",
                "E6",
                summary["previously_scanned"],
            ),
            ("G6", "New batch", "H6", summary["new_batch"]),
            (
                "J6",
                "Listings examined",
                "K6",
                summary["listings_examined"],
            ),
            (
                "M6",
                "Skipped seen",
                "N6",
                summary["skipped_seen"],
            ),
            (
                "P6",
                "History after",
                "Q6",
                summary["history_after"],
            ),
            (
                "S6",
                "Inventory status",
                "T6",
                summary["inventory_status"],
            ),
        ]

        label_fill = self._excel_rgb(217, 225, 242)
        value_fill = self._excel_rgb(242, 242, 242)

        for label_cell, label, value_cell, value in labels:
            sheet.Range(label_cell).Value = label
            sheet.Range(label_cell).Interior.Color = label_fill
            sheet.Range(label_cell).Font.Bold = True
            sheet.Range(value_cell).Value = value
            sheet.Range(value_cell).Interior.Color = value_fill

        sheet.Range("E4").NumberFormat = "yyyy-mm-dd hh:mm"
        sheet.Range("Q5").NumberFormat = "0.0%"
        sheet.Range("A4:T6").VerticalAlignment = XL_CENTER
        sheet.Range("T6").WrapText = True
        sheet.Rows(6).RowHeight = 30

    @staticmethod
    def _headers() -> list[str]:
        return [
            "Rank", "Decision", "Recommended Action", "Score",
            "Listing Type", "Seller", "Card Match", "Card ID", "Set",
            "Card Number", "Variant", "Rarity", "Listing Title", "Item ID",
            "Current Bid (£)", "Buy It Now (£)", "Postage (£)",
            "Bid Delivered (£)", "Buy Now Delivered (£)", "30-Day Average (£)",
            "Bid / Average", "Buy Now / Average", "Direct Listing",
            "Card Image", "Auction Search", "Buy Now Search",
            "Sold Comparables", "UK Market", "TCGplayer", "Cardmarket",
            "PriceCharting", *LONG_TERM_HEADERS,
            "Target Delivered (£)", "Maximum Bid (£)",
            "Bid Headroom (£)", "Buy Now Headroom (£)", "Bid Decision",
            "Buy Now Decision", "Ends At", "Minutes Remaining", "Bid Count",
            "Feedback %", "Feedback Count", "Condition", "Condition Flag",
            "Condition Details", "Match Confidence", "Search Query",
            "Status", "Notes", "Last Refreshed",
        ]

    @staticmethod
    def _result_row(
        rank: int,
        result: ListingResult,
        old_status: str,
    ) -> list[Any]:
        listing_image_url = str(
            getattr(result, "image_url", "") or ""
        ).strip()
        card_label = (
            f"{result.candidate.name} | "
            f"{result.candidate.set_name} | "
            f"{result.candidate.number} | "
            f"{result.candidate.variant}"
        )
        return [
            rank,
            result.decision,
            result.recommended_action,
            result.score,
            result.listing_type,
            result.seller,
            card_label,
            result.candidate.card_id,
            result.candidate.set_name,
            result.candidate.number,
            result.candidate.variant,
            result.candidate.rarity,
            result.title,
            result.item_id,
            result.current_bid,
            result.buy_now_price,
            result.postage,
            result.bid_delivered,
            result.buy_now_delivered,
            result.market_value,
            result.bid_ratio,
            result.buy_now_ratio,
            "Open Listing",
            (
                "Open Listing Image"
                if listing_image_url
                else (
                    "Open Card Image"
                    if result.candidate.image_url
                    else ""
                )
            ),
            "Open Auction Search",
            "Open Buy Now Search",
            "Open Sold Results",
            "Open UK Market",
            "Open TCGplayer",
            "Open Cardmarket",
            "Open PriceCharting",
            *assessment_values(result),
            result.target_delivered,
            result.maximum_bid,
            result.bid_headroom,
            result.buy_now_headroom,
            result.bid_decision,
            result.buy_now_decision,
            result.end_time.replace(tzinfo=None),
            result.minutes_remaining,
            result.bid_count,
            result.feedback_percent / 100,
            result.feedback_count,
            result.condition,
            result.condition_flag,
            result.condition_details,
            result.match_confidence,
            result.search_query,
            old_status or "NEW",
            result.notes,
            datetime.now(),
        ]

    def _format_table(
        self,
        sheet,
        result_count: int,
    ) -> None:
        header_fill = self._excel_rgb(31, 78, 121)
        header = sheet.Range("A8:BM8")
        header.Interior.Color = header_fill
        header.Font.Color = self._excel_rgb(255, 255, 255)
        header.Font.Bold = True
        header.HorizontalAlignment = XL_CENTER
        header.VerticalAlignment = XL_CENTER
        header.WrapText = True
        sheet.Rows(8).RowHeight = 52

        widths = [
            7, 11, 22, 9, 22, 18, 40, 17, 24, 12, 22, 17,
            52, 20, 13, 14, 11, 15, 17, 12, 13, 15,
            17, 17, 19, 19, 20, 16, 16, 16, 17,
            15, 24, 26, 18, 18, 19, 20, 21, 18, 20, 15, 25, 18, 55, 55,
            17, 15, 15, 18, 13, 15, 18, 16, 10, 14, 14, 28, 14, 48, 16, 35, 12, 55, 19,
        ]
        for column, width in enumerate(widths, start=1):
            sheet.Columns(column).ColumnWidth = width

        bottom = max(9, 8 + result_count)
        sheet.Range(sheet.Cells(9, 15), sheet.Cells(bottom, 20)).NumberFormat = "£0.00"
        sheet.Range(sheet.Cells(9, 21), sheet.Cells(bottom, 22)).NumberFormat = "0.0%"
        sheet.Range(sheet.Cells(9, 47), sheet.Cells(bottom, 50)).NumberFormat = "£0.00"
        sheet.Range(sheet.Cells(9, 53), sheet.Cells(bottom, 53)).NumberFormat = "yyyy-mm-dd hh:mm"
        sheet.Range(sheet.Cells(9, 56), sheet.Cells(bottom, 56)).NumberFormat = "0.0%"
        sheet.Range(sheet.Cells(9, 65), sheet.Cells(bottom, 65)).NumberFormat = "yyyy-mm-dd hh:mm"
        sheet.Range(sheet.Cells(9, 1), sheet.Cells(bottom, 65)).VerticalAlignment = XL_TOP
        sheet.Range(sheet.Cells(9, 5), sheet.Cells(bottom, 65)).WrapText = True

        self._set_validation(
            sheet.Range("BK9:BK2008"),
            [
                "NEW", "CHECKED", "WATCH", "BID", "BUY NOW",
                "REJECTED", "ENDED",
            ],
        )

        try:
            if sheet.AutoFilterMode:
                sheet.AutoFilterMode = False
            sheet.Range("A8:BM2008").AutoFilter()
        except Exception:
            pass

        try:
            sheet.Activate()
            self.excel.ActiveWindow.FreezePanes = False
            self.excel.ActiveWindow.SplitRow = 8
            self.excel.ActiveWindow.SplitColumn = 7
            self.excel.ActiveWindow.FreezePanes = True
        except Exception:
            pass

    def _write_unmatched(
        self,
        sheet,
        unmatched: list[dict[str, Any]],
        start_row: int,
    ) -> None:
        title_fill = self._excel_rgb(128, 100, 162)
        header_fill = self._excel_rgb(112, 48, 160)

        sheet.Range(
            sheet.Cells(start_row, 1),
            sheet.Cells(start_row, 10),
        ).Merge()
        sheet.Cells(start_row, 1).Value = (
            "Unmatched or excluded seller listings — manual review"
        )
        sheet.Range(
            sheet.Cells(start_row, 1),
            sheet.Cells(start_row, 10),
        ).Interior.Color = title_fill
        sheet.Range(
            sheet.Cells(start_row, 1),
            sheet.Cells(start_row, 10),
        ).Font.Color = self._excel_rgb(255, 255, 255)
        sheet.Range(
            sheet.Cells(start_row, 1),
            sheet.Cells(start_row, 10),
        ).Font.Bold = True

        header_row = start_row + 1
        headers = [
            "Rank",
            "Listing Title",
            "Item ID",
            "Listing Type",
            "Displayed Price (£)",
            "Postage (£)",
            "Ends At",
            "Reason",
            "Direct Listing",
            "Last Refreshed",
        ]
        sheet.Range(
            sheet.Cells(header_row, 1),
            sheet.Cells(header_row, 10),
        ).Value = (tuple(headers),)
        sheet.Range(
            sheet.Cells(header_row, 1),
            sheet.Cells(header_row, 10),
        ).Interior.Color = header_fill
        sheet.Range(
            sheet.Cells(header_row, 1),
            sheet.Cells(header_row, 10),
        ).Font.Color = self._excel_rgb(255, 255, 255)
        sheet.Range(
            sheet.Cells(header_row, 1),
            sheet.Cells(header_row, 10),
        ).Font.Bold = True

        if not unmatched:
            sheet.Cells(start_row + 2, 1).Value = (
                "All fetched listings were matched and evaluated."
            )
            return

        rows = []
        for index, item in enumerate(unmatched, start=1):
            rows.append(
                [
                    index,
                    item.get("title", ""),
                    item.get("item_id", ""),
                    item.get("listing_type", ""),
                    item.get("price"),
                    item.get("postage"),
                    item.get("end_time"),
                    item.get("reason", ""),
                    "Open Listing",
                    datetime.now(),
                ]
            )

        first = start_row + 2
        bottom = first + len(rows) - 1
        sheet.Range(
            sheet.Cells(first, 1),
            sheet.Cells(bottom, 10),
        ).Value = tuple(tuple(row) for row in rows)

        for offset, item in enumerate(unmatched):
            row = first + offset
            if item.get("item_url"):
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 9),
                    Address=item["item_url"],
                    TextToDisplay="Open Listing",
                )

        sheet.Range(
            sheet.Cells(first, 5),
            sheet.Cells(bottom, 6),
        ).NumberFormat = "£0.00"
        sheet.Range(
            sheet.Cells(first, 7),
            sheet.Cells(bottom, 7),
        ).NumberFormat = "yyyy-mm-dd hh:mm"
        sheet.Range(
            sheet.Cells(first, 10),
            sheet.Cells(bottom, 10),
        ).NumberFormat = "yyyy-mm-dd hh:mm"
        sheet.Range(
            sheet.Cells(first, 2),
            sheet.Cells(bottom, 10),
        ).WrapText = True

    def write_seller_radar(
        self,
        seller: str,
        results: list[ListingResult],
        unmatched: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> str:
        name = seller_sheet_name(seller)
        sheet, _ = self._get_or_add_sheet(name)
        old_statuses = self._existing_statuses(sheet)

        try:
            sheet.Cells.UnMerge()
        except Exception:
            pass
        try:
            sheet.Hyperlinks.Delete()
        except Exception:
            pass
        sheet.Cells.Clear()

        self._style_title(sheet, seller)
        self._write_summary(sheet, summary)

        headers = self._headers()
        sheet.Range("A8:BM8").Value = (tuple(headers),)

        rows = [
            self._result_row(
                rank,
                result,
                old_statuses.get(result.item_id, ""),
            )
            for rank, result in enumerate(results, start=1)
        ]

        if rows:
            bottom = 8 + len(rows)
            sheet.Range(
                sheet.Cells(9, 1),
                sheet.Cells(bottom, 65),
            ).Value = tuple(tuple(row) for row in rows)

            for offset, result in enumerate(results):
                row = 9 + offset

                self._style_decision_cell(
                    sheet.Cells(row, 2),
                    result.decision,
                )
                self._style_decision_cell(
                    sheet.Cells(row, 51),
                    result.bid_decision,
                )
                self._style_decision_cell(
                    sheet.Cells(row, 52),
                    result.buy_now_decision,
                )
                self._style_condition_cells(
                    sheet,
                    row,
                    condition_column=58,
                    flag_column=59,
                    flag=result.condition_flag,
                )
                self._style_investment_cells(
                    sheet,
                    row,
                    32,
                    33,
                    34,
                    result.long_term_score,
                )

                links = market_links_for_candidate(result.candidate)
                for column, address, label in (
                    (23, result.item_url, "Open Listing"),
                    (
                        24,
                        preferred_result_image(
                            getattr(result, "image_url", ""),
                            result.candidate.image_url,
                        ),
                        (
                            "Open Listing Image"
                            if getattr(result, "image_url", "")
                            else "Open Card Image"
                        ),
                    ),
                    (25, result.auction_search_url, "Open Auction Search"),
                    (26, result.buy_now_search_url, "Open Buy Now Search"),
                    (27, result.sold_search_url, "Open Sold Results"),
                    (28, links.uk_market, "Open UK Market"),
                    (29, links.tcgplayer, "Open TCGplayer"),
                    (30, links.cardmarket, "Open Cardmarket"),
                    (31, links.pricecharting, "Open PriceCharting"),
                ):
                    if address:
                        sheet.Hyperlinks.Add(
                            Anchor=sheet.Cells(row, column),
                            Address=address,
                            TextToDisplay=label,
                        )

        self._format_table(sheet, len(results))
        unmatched_start = max(
            12,
            8 + len(results) + 3,
        )
        self._write_unmatched(
            sheet,
            unmatched,
            unmatched_start,
        )

        try:
            sheet.Tab.Color = self._excel_rgb(
                112,
                48,
                160,
            )
        except Exception:
            pass

        return name
