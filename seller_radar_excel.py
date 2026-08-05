from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from random_sniper.core import ListingResult
from random_sniper.excel_adapter import ExcelAdapter


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
        for row in range(
            self.DATA_START_ROW,
            last_row + 1,
        ):
            item_id = str(
                sheet.Cells(row, 14).Value or ""
            ).strip()
            status = str(
                sheet.Cells(row, 44).Value or ""
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

        sheet.Range("A1:AT1").Merge()
        sheet.Cells(1, 1).Value = (
            f"Seller Radar — {seller}"
        )
        sheet.Range("A1:AT1").Interior.Color = navy
        sheet.Range("A1:AT1").Font.Color = self._excel_rgb(
            255,
            255,
            255,
        )
        sheet.Range("A1:AT1").Font.Bold = True
        sheet.Range("A1:AT1").Font.Size = 17
        sheet.Range("A1:AT1").VerticalAlignment = XL_CENTER
        sheet.Rows(1).RowHeight = 30

        sheet.Range("A2:AT2").Merge()
        sheet.Cells(2, 1).Value = (
            "Dedicated analysis of this seller's active Pokémon listings. "
            "Exact card matching, separate auction and Buy It Now outcomes, "
            "condition intelligence, market targets and native eBay links."
        )
        sheet.Range("A2:AT2").Interior.Color = pale
        sheet.Range("A2:AT2").WrapText = True
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
        sheet.Range("A4:T5").VerticalAlignment = XL_CENTER

    @staticmethod
    def _headers() -> list[str]:
        return [
            "Rank",
            "Decision",
            "Recommended Action",
            "Score",
            "Listing Type",
            "Seller",
            "Card Match",
            "Card ID",
            "Set",
            "Card Number",
            "Variant",
            "Rarity",
            "Listing Title",
            "Item ID",
            "Current Bid (£)",
            "Buy It Now (£)",
            "Postage (£)",
            "Bid Delivered (£)",
            "Buy Now Delivered (£)",
            "Market (£)",
            "Bid / Market",
            "Buy Now / Market",
            "Direct Listing",
            "Card Image",
            "Auction Search",
            "Buy Now Search",
            "Sold Comparables",
            "Target Delivered (£)",
            "Maximum Bid (£)",
            "Bid Headroom (£)",
            "Buy Now Headroom (£)",
            "Bid Decision",
            "Buy Now Decision",
            "Ends At",
            "Minutes Remaining",
            "Bid Count",
            "Feedback %",
            "Feedback Count",
            "Condition",
            "Condition Flag",
            "Condition Details",
            "Match Confidence",
            "Search Query",
            "Status",
            "Notes",
            "Last Refreshed",
        ]

    @staticmethod
    def _result_row(
        rank: int,
        result: ListingResult,
        old_status: str,
    ) -> list[Any]:
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
            "Open Card Image" if result.candidate.image_url else "",
            "Open Auction Search",
            "Open Buy Now Search",
            "Open Sold Results",
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
        header = sheet.Range("A8:AT8")
        header.Interior.Color = header_fill
        header.Font.Color = self._excel_rgb(255, 255, 255)
        header.Font.Bold = True
        header.HorizontalAlignment = XL_CENTER
        header.VerticalAlignment = XL_CENTER
        header.WrapText = True
        sheet.Rows(8).RowHeight = 45

        widths = {
            "A": 7, "B": 11, "C": 22, "D": 9, "E": 22, "F": 18,
            "G": 40, "H": 17, "I": 24, "J": 12, "K": 22, "L": 17,
            "M": 52, "N": 20, "O": 13, "P": 14, "Q": 11, "R": 15,
            "S": 17, "T": 12, "U": 13, "V": 15,
            "W": 17, "X": 17, "Y": 19, "Z": 19, "AA": 20,
            "AB": 17, "AC": 15, "AD": 15, "AE": 18,
            "AF": 13, "AG": 15, "AH": 18, "AI": 16, "AJ": 10,
            "AK": 12, "AL": 14, "AM": 28, "AN": 14, "AO": 48,
            "AP": 16, "AQ": 35, "AR": 12, "AS": 55, "AT": 19,
        }
        for column, width in widths.items():
            sheet.Columns(column).ColumnWidth = width

        bottom = max(9, 8 + result_count)
        sheet.Range(f"O9:T{bottom}").NumberFormat = "£0.00"
        sheet.Range(f"U9:V{bottom}").NumberFormat = "0.0%"
        sheet.Range(f"AB9:AE{bottom}").NumberFormat = "£0.00"
        sheet.Range(f"AH9:AH{bottom}").NumberFormat = "yyyy-mm-dd hh:mm"
        sheet.Range(f"AK9:AK{bottom}").NumberFormat = "0.0%"
        sheet.Range(f"AT9:AT{bottom}").NumberFormat = "yyyy-mm-dd hh:mm"
        sheet.Range(f"A9:AT{bottom}").VerticalAlignment = XL_TOP
        sheet.Range(f"E9:AT{bottom}").WrapText = True

        self._set_validation(
            sheet.Range("AR9:AR2008"),
            [
                "NEW",
                "CHECKED",
                "WATCH",
                "BID",
                "BUY NOW",
                "REJECTED",
                "ENDED",
            ],
        )

        try:
            if sheet.AutoFilterMode:
                sheet.AutoFilterMode = False
            sheet.Range("A8:AT2008").AutoFilter()
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
        sheet.Range("A8:AT8").Value = (tuple(headers),)

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
                sheet.Cells(bottom, 46),
            ).Value = tuple(tuple(row) for row in rows)

            for offset, result in enumerate(results):
                row = 9 + offset

                self._style_decision_cell(
                    sheet.Cells(row, 2),
                    result.decision,
                )
                self._style_decision_cell(
                    sheet.Cells(row, 32),
                    result.bid_decision,
                )
                self._style_decision_cell(
                    sheet.Cells(row, 33),
                    result.buy_now_decision,
                )
                self._style_condition_cells(
                    sheet,
                    row,
                    condition_column=39,
                    flag_column=40,
                    flag=result.condition_flag,
                )

                if result.item_url:
                    sheet.Hyperlinks.Add(
                        Anchor=sheet.Cells(row, 23),
                        Address=result.item_url,
                        TextToDisplay="Open Listing",
                    )
                if result.candidate.image_url:
                    sheet.Hyperlinks.Add(
                        Anchor=sheet.Cells(row, 24),
                        Address=result.candidate.image_url,
                        TextToDisplay="Open Card Image",
                    )
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 25),
                    Address=result.auction_search_url,
                    TextToDisplay="Open Auction Search",
                )
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 26),
                    Address=result.buy_now_search_url,
                    TextToDisplay="Open Buy Now Search",
                )
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 27),
                    Address=result.sold_search_url,
                    TextToDisplay="Open Sold Results",
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
