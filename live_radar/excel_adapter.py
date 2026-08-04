from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .core import (
    Candidate,
    RadarResult,
    RadarSettings,
    normalize_card_number,
)


XL_UP = -4162
XL_TO_LEFT = -4159
XL_TOP = -4160
XL_LEFT = -4131
XL_CENTER = -4108


class ExcelAdapter:
    def __init__(self, workbook_path: Path) -> None:
        import win32com.client

        self.workbook_path = workbook_path
        self.excel = win32com.client.DispatchEx(
            "Excel.Application"
        )
        self.excel.Visible = False
        self.excel.DisplayAlerts = False
        self.excel.ScreenUpdating = False
        self.excel.EnableEvents = False
        self.book = self.excel.Workbooks.Open(
            str(workbook_path.resolve())
        )

    def close(self, save: bool = True) -> None:
        try:
            self.book.Close(SaveChanges=save)
        finally:
            self.excel.EnableEvents = True
            self.excel.ScreenUpdating = True
            self.excel.Quit()

    def save(self) -> None:
        self.book.Save()

    def sheet(self, name: str):
        return self.book.Worksheets(name)

    @staticmethod
    def _last_row(sheet, column: int = 1) -> int:
        return max(
            1,
            int(
                sheet.Cells(
                    sheet.Rows.Count,
                    column,
                ).End(XL_UP).Row
            ),
        )

    @staticmethod
    def _rows(value: Any) -> list[tuple[Any, ...]]:
        if value is None:
            return []
        if isinstance(value, tuple):
            if value and isinstance(value[0], tuple):
                return list(value)
            return [value]
        return [(value,)]

    @staticmethod
    def _bool(value: Any, default: bool) -> bool:
        if value in (None, ""):
            return default
        return str(value).strip().upper() == "YES"

    @staticmethod
    def _ratio(value: Any, default: float) -> float:
        if value in (None, ""):
            return default
        number = float(value)
        return number if number <= 1 else number / 100

    def read_settings(self) -> RadarSettings:
        sheet = self.sheet("Scanner Settings")
        values = {
            str(sheet.Cells(row, 1).Value or "").strip():
            sheet.Cells(row, 2).Value
            for row in range(4, 35)
        }

        return RadarSettings(
            enabled=self._bool(
                values.get("Enabled"),
                True,
            ),
            target_ratio=self._ratio(
                values.get("Green purchase ratio"),
                0.75,
            ),
            amber_upper_ratio=self._ratio(
                values.get("Amber upper ratio"),
                0.90,
            ),
            minimum_market_value=float(
                values.get("Minimum market value (£)") or 3
            ),
            maximum_delivered_cost=float(
                values.get("Maximum delivered cost (£)") or 100
            ),
            results_per_request=int(
                values.get("Radar results per request") or 200
            ),
            maximum_broad_requests=int(
                values.get("Maximum broad search requests") or 5
            ),
            minimum_minutes_remaining=int(
                values.get("Minimum minutes remaining") or 2
            ),
            maximum_hours_remaining=float(
                values.get("Ending within hours") or 24
            ),
            minimum_feedback=float(
                values.get("Minimum seller feedback (%)") or 98
            ),
            minimum_feedback_count=int(
                values.get("Minimum seller feedback count") or 25
            ),
            maximum_total_api_calls=int(
                values.get("Maximum total API calls") or 100
            ),
            maximum_live_rows=int(
                values.get("Maximum live rows") or 250
            ),
            broad_query=str(
                values.get("Broad radar query") or "pokemon card"
            ).strip(),
            expand_green_sellers=self._bool(
                values.get("Expand GREEN sellers"),
                True,
            ),
            maximum_green_sellers=int(
                values.get("Maximum GREEN sellers") or 5
            ),
            seller_listing_limit=int(
                values.get("Seller listings to inspect") or 100
            ),
            opportunities_per_seller=int(
                values.get("Opportunities per seller") or 5
            ),
            maximum_condition_checks=int(
                values.get("Detailed condition checks") or 50
            ),
            archive_previous_results=self._bool(
                values.get("Archive previous live results"),
                True,
            ),
        )

    def read_candidates(self) -> list[Candidate]:
        database = self._read_database_details()
        sheet = self.sheet("Market Data Import")
        last_row = self._last_row(sheet, 1)
        values = self._rows(
            sheet.Range(f"A5:L{last_row}").Value
        )

        candidates: list[Candidate] = []
        for row in values:
            if str(row[0] or "").strip().upper() != "YES":
                continue

            name = str(row[1] or "").strip()
            set_name = str(row[2] or "").strip()
            number = normalize_card_number(row[3])
            variant = str(row[4] or "").strip()
            language = str(row[5] or "").strip()

            if language and language.casefold() != "english":
                continue

            try:
                market_value = float(row[7] or 0)
            except (TypeError, ValueError):
                continue
            if market_value <= 0:
                continue

            details = database.get(
                (
                    name.casefold(),
                    set_name.casefold(),
                    number.casefold(),
                ),
                {},
            )

            candidates.append(
                Candidate(
                    card_id=str(
                        details.get("card_id", "") or ""
                    ),
                    name=name,
                    set_name=set_name,
                    number=number,
                    variant=variant,
                    market_value=market_value,
                    source=str(row[8] or ""),
                    source_date=row[9],
                    source_url=str(row[10] or ""),
                    rarity=str(
                        details.get("rarity", "") or ""
                    ),
                    supertype=str(
                        details.get("supertype", "") or ""
                    ),
                    image_url=str(
                        details.get("image_url", "") or ""
                    ),
                )
            )

        return candidates

    def _read_database_details(
        self,
    ) -> dict[tuple[str, str, str], dict[str, Any]]:
        sheet = self.sheet("Full Card Database")
        last_row = self._last_row(sheet, 1)
        values = self._rows(
            sheet.Range(f"A5:AF{last_row}").Value
        )

        output: dict[
            tuple[str, str, str],
            dict[str, Any],
        ] = {}

        for row in values:
            name = str(row[1] or "").strip()
            set_name = str(row[3] or "").strip()
            number = normalize_card_number(row[5])
            output[
                (
                    name.casefold(),
                    set_name.casefold(),
                    number.casefold(),
                )
            ] = {
                "card_id": str(row[0] or "").strip(),
                "rarity": str(row[7] or "").strip(),
                "supertype": str(row[8] or "").strip(),
                "image_url": str(row[29] or "").strip(),
            }

        return output

    @staticmethod
    def _excel_rgb(red: int, green: int, blue: int) -> int:
        return red + green * 256 + blue * 65536

    def _style_flag(self, cell, value: str) -> None:
        value = str(value or "N/A").upper()
        if value == "GREEN":
            fill = self._excel_rgb(198, 239, 206)
            font = self._excel_rgb(0, 97, 0)
        elif value == "AMBER":
            fill = self._excel_rgb(255, 235, 156)
            font = self._excel_rgb(156, 101, 0)
        elif value == "RED":
            fill = self._excel_rgb(255, 199, 206)
            font = self._excel_rgb(156, 0, 6)
        else:
            fill = self._excel_rgb(217, 217, 217)
            font = self._excel_rgb(89, 89, 89)

        cell.Interior.Color = fill
        cell.Font.Color = font
        cell.Font.Bold = True
        cell.HorizontalAlignment = XL_CENTER

    def archive_current_live_results(self) -> int:
        live = self.sheet("Live Opportunities")
        last_row = self._last_row(live, 1)
        if last_row < 5:
            return 0

        archive = self.sheet("Opportunity Archive")
        target_row = max(
            4,
            self._last_row(archive, 1) + 1,
        )
        row_count = last_row - 4

        source_values = self._rows(
            live.Range(f"A5:AN{last_row}").Value
        )

        archive_rows = []
        for offset, original in enumerate(source_values):
            if not any(
                value not in (None, "")
                for value in original
            ):
                continue

            row_number = 5 + offset
            row = list(original[:40])

            # Preserve the actual URLs rather than only the visible
            # "Open..." hyperlink labels.
            for zero_index, column_number in (
                (19, 20),
                (20, 21),
                (21, 22),
                (22, 23),
            ):
                try:
                    hyperlink = live.Cells(
                        row_number,
                        column_number,
                    ).Hyperlinks(1)
                    if hyperlink.Address:
                        row[zero_index] = hyperlink.Address
                except Exception:
                    pass

            archive_rows.append(
                [
                    datetime.now(),
                    str(row[37] or "ARCHIVED"),
                    *row,
                ]
            )
        if not archive_rows:
            return 0

        bottom = target_row + len(archive_rows) - 1
        archive.Range(
            archive.Cells(target_row, 1),
            archive.Cells(bottom, 42),
        ).Value = tuple(tuple(row) for row in archive_rows)
        return len(archive_rows)

    @staticmethod
    def _result_row(
        rank: int,
        result: RadarResult,
    ) -> list[Any]:
        return [
            rank,
            result.decision,
            result.recommended_action,
            result.score,
            result.discovery_source,
            result.parent_item_id,
            result.card_label,
            result.candidate.card_id,
            result.candidate.set_name,
            result.candidate.number,
            result.candidate.variant,
            result.candidate.rarity,
            result.title,
            result.item_id,
            result.current_bid,
            result.postage,
            result.delivered,
            result.market_value,
            result.ratio,
            "Open Listing",
            "Open Card Image" if result.candidate.image_url else "",
            "Open Auction Search",
            "Open Sold Results",
            result.target_delivered,
            result.maximum_bid,
            result.bid_headroom,
            result.end_time.replace(tzinfo=None),
            result.minutes_remaining,
            result.bid_count,
            result.seller,
            result.feedback_percent / 100,
            result.feedback_count,
            result.condition,
            result.condition_flag,
            result.condition_details,
            result.match_confidence,
            result.search_query,
            "NEW",
            result.notes,
            datetime.now(),
        ]

    def write_results(
        self,
        results: list[RadarResult],
    ) -> None:
        sheet = self.sheet("Live Opportunities")
        sheet.Range("A5:AN1004").ClearContents()
        try:
            sheet.Range("T5:W1004").Hyperlinks.Delete()
        except Exception:
            pass

        rows = [
            self._result_row(rank, result)
            for rank, result in enumerate(results, start=1)
        ]
        if not rows:
            return

        bottom = 4 + len(rows)
        sheet.Range(
            sheet.Cells(5, 1),
            sheet.Cells(bottom, 40),
        ).Value = tuple(tuple(row) for row in rows)

        for offset, result in enumerate(results):
            row = 5 + offset

            if result.discovery_source == "↳ SAME SELLER":
                whole_row = sheet.Range(
                    sheet.Cells(row, 1),
                    sheet.Cells(row, 40),
                )
                whole_row.Interior.Color = self._excel_rgb(
                    221,
                    235,
                    247,
                )
                whole_row.Font.Color = self._excel_rgb(
                    31,
                    78,
                    121,
                )
                whole_row.Font.Italic = True

            self._style_flag(
                sheet.Cells(row, 2),
                result.decision,
            )
            self._style_flag(
                sheet.Cells(row, 33),
                result.condition_flag,
            )
            self._style_flag(
                sheet.Cells(row, 34),
                result.condition_flag,
            )
            sheet.Cells(row, 33).HorizontalAlignment = XL_LEFT

            sheet.Hyperlinks.Add(
                Anchor=sheet.Cells(row, 20),
                Address=result.item_url,
                TextToDisplay="Open Listing",
            )
            if result.candidate.image_url:
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 21),
                    Address=result.candidate.image_url,
                    TextToDisplay="Open Card Image",
                )
            sheet.Hyperlinks.Add(
                Anchor=sheet.Cells(row, 22),
                Address=result.direct_search_url,
                TextToDisplay="Open Auction Search",
            )
            sheet.Hyperlinks.Add(
                Anchor=sheet.Cells(row, 23),
                Address=result.sold_search_url,
                TextToDisplay="Open Sold Results",
            )

    def append_log(
        self,
        broad_requests: int,
        raw_results: int,
        unique_results: int,
        green: int,
        amber: int,
        message: str,
        success: bool = True,
    ) -> None:
        sheet = self.sheet("Scanner Log")
        row = max(4, self._last_row(sheet, 1) + 1)
        sheet.Range(f"A{row}:H{row}").Value = (
            (
                datetime.now(),
                "LIVE-RADAR" if success else "LIVE-RADAR-ERROR",
                broad_requests,
                raw_results,
                unique_results,
                green,
                amber,
                message[:1000],
            ),
        )

    def update_dashboard(
        self,
        results: list[RadarResult],
    ) -> None:
        try:
            sheet = self.sheet("Scanner Dashboard")
        except Exception:
            return

        green = sum(
            result.decision == "GREEN"
            for result in results
        )
        amber = sum(
            result.decision == "AMBER"
            for result in results
        )
        average_score = (
            sum(result.score for result in results) / len(results)
            if results
            else 0
        )
        best_headroom = max(
            (
                result.bid_headroom
                for result in results
            ),
            default=0,
        )

        sheet.Cells(4, 2).Value = datetime.now()
        sheet.Cells(5, 2).Value = len(results)
        sheet.Cells(6, 2).Value = green
        sheet.Cells(7, 2).Value = amber
        sheet.Cells(8, 2).Value = 0
        sheet.Cells(9, 2).Value = average_score
        sheet.Cells(10, 2).Value = best_headroom
