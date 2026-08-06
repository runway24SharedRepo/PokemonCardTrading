from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from ai_review_logic import normalise
from ai_review_models import CandidateOption, ListingRow, ReviewExecution


XL_UP = -4162
XL_TO_LEFT = -4159
XL_CENTER = -4108

AI_HEADERS = [
    "AI Review Request",
    "AI Review Status",
    "AI Action",
    "AI Identity Verdict",
    "AI Selected Candidate",
    "AI Confidence %",
    "AI Edition Verdict",
    "AI Variant Verdict",
    "AI Listing Risk",
    "AI Risk Flags",
    "AI Condition Summary",
    "AI Long-Term Note",
    "AI Evidence",
    "AI Model",
    "AI Input Tokens",
    "AI Output Tokens",
    "AI Estimated Cost ($)",
    "AI Reviewed At",
    "AI Reviewed Item ID",
]

ACTIVE_SHEETS = {
    "Random Snipe Results": (4, 5),
    "Random Snipe Queue": (4, 5),
    "Snipe Queue": (4, 5),
    "Live Opportunities": (4, 5),
}
ARCHIVE_SHEETS = {
    "Random Snipe History": (4, 5),
    "Opportunity Archive": (3, 4),
}


def _as_rows(value: Any) -> list[list[Any]]:
    if value is None:
        return []
    if not isinstance(value, tuple):
        return [[value]]
    if value and not isinstance(value[0], tuple):
        return [list(value)]
    return [list(row) for row in value]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class AIExcelAdapter:
    def __init__(self, workbook_path: Path) -> None:
        import win32com.client

        self.workbook_path = workbook_path
        self.excel = win32com.client.DispatchEx("Excel.Application")
        self.excel.Visible = False
        self.excel.DisplayAlerts = False
        self.excel.ScreenUpdating = False
        self.excel.EnableEvents = False
        self.book = self.excel.Workbooks.Open(str(workbook_path.resolve()))

    @staticmethod
    def rgb(red: int, green: int, blue: int) -> int:
        return red + green * 256 + blue * 65536

    def save(self) -> None:
        self.book.Save()

    def close(self, save: bool = True) -> None:
        try:
            self.book.Close(SaveChanges=save)
        finally:
            self.excel.Quit()

    def _sheet_or_none(self, name: str):
        try:
            return self.book.Worksheets(name)
        except Exception:
            return None

    def _get_or_add_sheet(self, name: str):
        sheet = self._sheet_or_none(name)
        if sheet is not None:
            return sheet
        sheet = self.book.Worksheets.Add(
            After=self.book.Worksheets(self.book.Worksheets.Count)
        )
        sheet.Name = name
        return sheet

    @staticmethod
    def _last_row(sheet, column: int) -> int:
        return max(1, int(sheet.Cells(sheet.Rows.Count, column).End(XL_UP).Row))

    @staticmethod
    def _last_header_column(sheet, header_row: int) -> int:
        return max(
            1,
            int(sheet.Cells(header_row, sheet.Columns.Count).End(XL_TO_LEFT).Column),
        )

    @staticmethod
    def _header_map(sheet, header_row: int) -> dict[str, int]:
        last_column = AIExcelAdapter._last_header_column(sheet, header_row)
        values = _as_rows(
            sheet.Range(
                sheet.Cells(header_row, 1), sheet.Cells(header_row, last_column)
            ).Value
        )
        row = values[0] if values else []
        return {
            normalise(value): index
            for index, value in enumerate(row, start=1)
            if _text(value)
        }

    @staticmethod
    def _find_column(headers: dict[str, int], names: Iterable[str]) -> int | None:
        for name in names:
            column = headers.get(normalise(name))
            if column:
                return column
        return None

    def ensure_ai_columns(
        self,
        sheet,
        header_row: int,
        data_start_row: int,
    ) -> dict[str, int]:
        headers = self._header_map(sheet, header_row)
        existing_start = headers.get(normalise(AI_HEADERS[0]))
        start_column = (
            existing_start
            if existing_start
            else self._last_header_column(sheet, header_row) + 1
        )
        end_column = start_column + len(AI_HEADERS) - 1
        sheet.Range(
            sheet.Cells(header_row, start_column),
            sheet.Cells(header_row, end_column),
        ).Value = (tuple(AI_HEADERS),)
        header = sheet.Range(
            sheet.Cells(header_row, start_column),
            sheet.Cells(header_row, end_column),
        )
        header.Interior.Color = self.rgb(91, 33, 182)
        header.Font.Color = self.rgb(255, 255, 255)
        header.Font.Bold = True
        header.WrapText = True
        header.HorizontalAlignment = XL_CENTER
        widths = [
            16, 16, 15, 18, 28, 14, 20, 19, 15, 42,
            44, 48, 56, 18, 13, 13, 18, 19, 22,
        ]
        for offset, width in enumerate(widths):
            sheet.Columns(start_column + offset).ColumnWidth = width
        try:
            validation_range = sheet.Range(
                sheet.Cells(data_start_row, start_column),
                sheet.Cells(data_start_row + 5000, start_column),
            )
            try:
                validation_range.Validation.Delete()
            except Exception:
                pass
            validation_range.Validation.Add(
                Type=3, AlertStyle=1, Operator=1, Formula1="AUTO,YES,NO"
            )
            validation_range.Validation.InCellDropdown = True
        except Exception:
            pass
        return {header: start_column + index for index, header in enumerate(AI_HEADERS)}

    def ensure_settings_sheet(self) -> None:
        sheet = self._get_or_add_sheet("AI Review Settings")
        preserved: dict[str, Any] = {}
        try:
            existing = _as_rows(sheet.Range("A5:B40").Value)
            preserved = {
                _text(row[0]): row[1]
                for row in existing
                if len(row) >= 2 and _text(row[0])
            }
        except Exception:
            preserved = {}
        try:
            sheet.Cells.UnMerge()
        except Exception:
            pass
        sheet.Cells.Clear()
        sheet.Range("A1:H1").Merge()
        sheet.Cells(1, 1).Value = "Phase 5.6 — Text-Only AI Listing Intelligence"
        sheet.Range("A1:H1").Interior.Color = self.rgb(91, 33, 182)
        sheet.Range("A1:H1").Font.Color = self.rgb(255, 255, 255)
        sheet.Range("A1:H1").Font.Bold = True
        sheet.Range("A1:H1").Font.Size = 17
        sheet.Rows(1).RowHeight = 30
        sheet.Range("A2:H2").Merge()
        sheet.Cells(2, 1).Value = (
            "Images are disabled. AI reviews listing text and a restricted "
            "candidate shortlist. It never silently changes card identity or price."
        )
        sheet.Range("A2:H2").WrapText = True
        sheet.Range("A2:H2").Interior.Color = self.rgb(237, 233, 254)
        sheet.Rows(2).RowHeight = 42
        sheet.Range("A4:D4").Value = (("Setting", "Value", "Description", "Editable"),)
        sheet.Range("A4:D4").Interior.Color = self.rgb(76, 29, 149)
        sheet.Range("A4:D4").Font.Color = self.rgb(255, 255, 255)
        sheet.Range("A4:D4").Font.Bold = True
        settings = [
            ("AI Enabled", "YES", "Master on/off switch.", "YES"),
            (
                "Model",
                "gpt-5.6-luna",
                "Supported: gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol.",
                "YES",
            ),
            ("Reasoning Effort", "low", "none, low, medium, high, xhigh or max.", "YES"),
            ("Maximum Reviews Per Run", 20, "Hard maximum of new API calls per run.", "YES"),
            ("Monthly Budget USD", 5.00, "Local estimated monthly-spend stop.", "YES"),
            ("Reserve Per Review USD", 0.05, "Conservative reserve before a new call.", "YES"),
            ("Minimum Market Value GBP", 20.00, "Smart review value threshold.", "YES"),
            ("Review Decisions", "GREEN,AMBER", "Financial decisions eligible in smart mode.", "YES"),
            ("Review Low Confidence", "YES", "Review uncertain deterministic matches.", "YES"),
            ("Review Risk Terms", "YES", "Review proxy/custom/lot/novelty wording.", "YES"),
            ("Review Edition Terms", "YES", "Review First Edition, Unlimited and Shadowless.", "YES"),
            ("Include Archives", "NO", "Include history/archive sheets in smart mode.", "YES"),
            ("Fetch eBay Text Details", "YES", "Fetch descriptions, condition and item specifics.", "YES"),
            ("Urgent Maximum Minutes", 180, "Queue urgent-review time window.", "YES"),
            ("Auto Accept Confidence", 95, "Minimum confidence for KEEP.", "YES"),
            ("Maximum Output Tokens", 650, "Maximum structured response tokens.", "YES"),
            ("Image Review Enabled", "NO", "Locked off. No images are sent.", "NO"),
        ]
        settings = [
            (name, preserved.get(name, value), description, editable)
            for name, value, description, editable in settings
        ]
        sheet.Range("A5:D21").Value = tuple(tuple(row) for row in settings)
        sheet.Range("B5:B21").Interior.Color = self.rgb(255, 251, 235)
        sheet.Range("A5:A21").Font.Bold = True
        sheet.Range("C5:C21").WrapText = True
        sheet.Range("F4:H4").Value = (("Usage Summary", "Value", "Updated"),)
        sheet.Range("F4:H4").Interior.Color = self.rgb(76, 29, 149)
        sheet.Range("F4:H4").Font.Color = self.rgb(255, 255, 255)
        sheet.Range("F4:H4").Font.Bold = True
        summary = [
            ("Current Month Spend ($)", 0.0, ""),
            ("Reviews This Run", 0, ""),
            ("Cache Hits This Run", 0, ""),
            ("Rows Skipped", 0, ""),
            ("API Errors", 0, ""),
            ("Last Run Mode", "", ""),
        ]
        sheet.Range("F5:H10").Value = tuple(tuple(row) for row in summary)
        sheet.Columns("A").ColumnWidth = 30
        sheet.Columns("B").ColumnWidth = 22
        sheet.Columns("C").ColumnWidth = 62
        sheet.Columns("D").ColumnWidth = 12
        sheet.Columns("F").ColumnWidth = 28
        sheet.Columns("G").ColumnWidth = 18
        sheet.Columns("H").ColumnWidth = 20
        sheet.Range("G5").NumberFormat = "$0.0000"
        try:
            sheet.Tab.Color = self.rgb(91, 33, 182)
        except Exception:
            pass

    def ensure_log_sheet(self) -> None:
        sheet = self._get_or_add_sheet("AI Review Log")
        headers = [
            "Reviewed At", "Source Sheet", "Source Row", "Item ID", "Listing Title",
            "Current Candidate", "AI Selected Candidate", "Status", "Action",
            "Identity Verdict", "Confidence %", "Edition Verdict", "Variant Verdict",
            "Listing Risk", "Risk Flags", "Condition Summary", "Long-Term Note",
            "Evidence", "Model", "Input Tokens", "Output Tokens", "Estimated Cost ($)",
            "Cache", "Response ID",
        ]
        if _text(sheet.Cells(1, 1).Value) != headers[0]:
            sheet.Cells.Clear()
            sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, len(headers))).Value = (tuple(headers),)
        header = sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, len(headers)))
        header.Interior.Color = self.rgb(76, 29, 149)
        header.Font.Color = self.rgb(255, 255, 255)
        header.Font.Bold = True
        header.WrapText = True
        widths = [19, 24, 10, 23, 58, 34, 34, 16, 16, 18, 14, 20, 19, 15, 42, 44, 48, 60, 18, 13, 13, 18, 10, 24]
        for index, width in enumerate(widths, start=1):
            sheet.Columns(index).ColumnWidth = width
        try:
            sheet.Activate()
            self.excel.ActiveWindow.SplitRow = 1
            self.excel.ActiveWindow.FreezePanes = True
        except Exception:
            pass

    def ensure_all_structure(self) -> list[str]:
        self.ensure_settings_sheet()
        self.ensure_log_sheet()
        updated: list[str] = []
        for name, (header_row, data_start) in {**ACTIVE_SHEETS, **ARCHIVE_SHEETS}.items():
            sheet = self._sheet_or_none(name)
            if sheet is None:
                continue
            self.ensure_ai_columns(sheet, header_row, data_start)
            updated.append(name)
        for sheet in self.book.Worksheets:
            name = str(sheet.Name)
            if name.startswith("Seller - "):
                self.ensure_ai_columns(sheet, 8, 9)
                updated.append(name)
        return updated

    def read_settings(self) -> dict[str, Any]:
        sheet = self._sheet_or_none("AI Review Settings")
        if sheet is None:
            self.ensure_settings_sheet()
            sheet = self._sheet_or_none("AI Review Settings")
        values = _as_rows(sheet.Range("A5:B40").Value)
        return {
            _text(row[0]): row[1]
            for row in values
            if len(row) >= 2 and _text(row[0])
        }

    def update_usage_summary(
        self,
        *,
        month_spend: float,
        reviews: int,
        cache_hits: int,
        skipped: int,
        errors: int,
        mode: str,
    ) -> None:
        sheet = self._sheet_or_none("AI Review Settings")
        if sheet is None:
            return
        now = datetime.now()
        sheet.Range("G5:H10").Value = (
            (month_spend, now),
            (reviews, now),
            (cache_hits, now),
            (skipped, now),
            (errors, now),
            (mode, now),
        )
        sheet.Range("G5").NumberFormat = "$0.0000"
        sheet.Range("H5:H10").NumberFormat = "yyyy-mm-dd hh:mm"

    def read_market_candidates(self) -> list[CandidateOption]:
        market = self._sheet_or_none("Market Data Import")
        database = self._sheet_or_none("Full Card Database")
        if market is None or database is None:
            raise RuntimeError("Market Data Import or Full Card Database is missing.")
        db_last = self._last_row(database, 1)
        db_values = _as_rows(database.Range(f"A5:F{db_last}").Value)
        card_ids: dict[tuple[str, str, str], str] = {}
        for row in db_values:
            if len(row) < 6:
                continue
            card_ids[(normalise(row[1]), normalise(row[3]), normalise(row[5]))] = _text(row[0])
        market_last = self._last_row(market, 2)
        values = _as_rows(market.Range(f"A5:H{market_last}").Value)
        output: list[CandidateOption] = []
        seen: set[str] = set()
        for row in values:
            if len(row) < 8:
                continue
            enabled = _text(row[0]).upper()
            if enabled not in {"", "YES", "TRUE", "1"}:
                continue
            name, set_name, number, variant = map(_text, row[1:5])
            card_id = card_ids.get((normalise(name), normalise(set_name), normalise(number)), "")
            if not card_id:
                continue
            candidate_key = f"{card_id}::{variant}"
            if candidate_key in seen:
                continue
            seen.add(candidate_key)
            output.append(
                CandidateOption(
                    candidate_key=candidate_key,
                    card_id=card_id,
                    card_name=name,
                    set_name=set_name,
                    card_number=number,
                    variant=variant,
                    market_value_gbp=_float(row[7]),
                )
            )
        return output

    def _sheet_specs(self, include_archives: bool) -> list[tuple[Any, int, int]]:
        specs = dict(ACTIVE_SHEETS)
        if include_archives:
            specs.update(ARCHIVE_SHEETS)
        output: list[tuple[Any, int, int]] = []
        for name, (header, start) in specs.items():
            sheet = self._sheet_or_none(name)
            if sheet is not None:
                output.append((sheet, header, start))
        for sheet in self.book.Worksheets:
            if str(sheet.Name).startswith("Seller - "):
                output.append((sheet, 8, 9))
        return output

    def collect_rows(self, include_archives: bool) -> list[ListingRow]:
        output: list[ListingRow] = []
        for sheet, header_row, data_start in self._sheet_specs(include_archives):
            ai_columns = self.ensure_ai_columns(sheet, header_row, data_start)
            headers = self._header_map(sheet, header_row)
            item_column = self._find_column(headers, ["Item ID"])
            title_column = self._find_column(headers, ["Listing Title", "Title"])
            if item_column is None or title_column is None:
                continue
            last = self._last_row(sheet, item_column)
            if last < data_start:
                continue

            def column(*names: str) -> int | None:
                return self._find_column(headers, names)

            card_id_col = column("Card ID")
            card_match_col = column("Card Match", "Selected Card")
            set_col = column("Set")
            number_col = column("Card Number")
            variant_col = column("Variant")
            market_col = column("Market (£)", "Market Value (£)")
            decision_col = column("Decision")
            confidence_col = column("Match Confidence")
            condition_col = column("Condition")
            condition_details_col = column("Condition Details")
            seller_col = column("Seller")
            minutes_col = column("Minutes Remaining")

            for row_number in range(data_start, last + 1):
                item_id = _text(sheet.Cells(row_number, item_column).Value)
                title = _text(sheet.Cells(row_number, title_column).Value)
                if not item_id or not title:
                    continue
                card_match = _text(sheet.Cells(row_number, card_match_col).Value) if card_match_col else ""
                parts = [part.strip() for part in card_match.split("|")]
                card_name = parts[0] if parts else ""
                set_name = (
                    _text(sheet.Cells(row_number, set_col).Value)
                    if set_col else (parts[1] if len(parts) >= 2 else "")
                )
                card_number = (
                    _text(sheet.Cells(row_number, number_col).Value)
                    if number_col else (parts[2] if len(parts) >= 3 else "")
                )
                variant = (
                    _text(sheet.Cells(row_number, variant_col).Value)
                    if variant_col else (parts[3] if len(parts) >= 4 else "")
                )
                output.append(
                    ListingRow(
                        sheet_name=str(sheet.Name),
                        row_number=row_number,
                        header_row=header_row,
                        item_id=item_id,
                        title=title,
                        card_id=_text(sheet.Cells(row_number, card_id_col).Value) if card_id_col else "",
                        card_name=card_name,
                        set_name=set_name,
                        card_number=card_number,
                        variant=variant,
                        market_value_gbp=_float(sheet.Cells(row_number, market_col).Value) if market_col else 0.0,
                        decision=_text(sheet.Cells(row_number, decision_col).Value) if decision_col else "",
                        match_confidence=_text(sheet.Cells(row_number, confidence_col).Value) if confidence_col else "",
                        condition=_text(sheet.Cells(row_number, condition_col).Value) if condition_col else "",
                        condition_details=_text(sheet.Cells(row_number, condition_details_col).Value) if condition_details_col else "",
                        seller=_text(sheet.Cells(row_number, seller_col).Value) if seller_col else "",
                        minutes_remaining=(
                            _float(sheet.Cells(row_number, minutes_col).Value, default=10**9)
                            if minutes_col else None
                        ),
                        review_request=_text(
                            sheet.Cells(row_number, ai_columns["AI Review Request"]).Value
                        ) or "AUTO",
                        ai_columns=ai_columns,
                    )
                )
        return output

    def clear_stale_ai(self, row: ListingRow) -> None:
        sheet = self._sheet_or_none(row.sheet_name)
        if sheet is None:
            return
        old_item = _text(
            sheet.Cells(row.row_number, row.ai_columns["AI Reviewed Item ID"]).Value
        )
        if old_item and old_item != row.item_id:
            sheet.Range(
                sheet.Cells(row.row_number, row.ai_columns["AI Review Status"]),
                sheet.Cells(row.row_number, row.ai_columns["AI Reviewed Item ID"]),
            ).ClearContents()

    def write_status(self, row: ListingRow, status: str, action: str = "", note: str = "") -> None:
        sheet = self._sheet_or_none(row.sheet_name)
        if sheet is None:
            return
        columns = row.ai_columns
        sheet.Cells(row.row_number, columns["AI Review Status"]).Value = status
        if action:
            sheet.Cells(row.row_number, columns["AI Action"]).Value = action
        if note:
            sheet.Cells(row.row_number, columns["AI Evidence"]).Value = note
        sheet.Cells(row.row_number, columns["AI Reviewed Item ID"]).Value = row.item_id

    def write_review(
        self,
        row: ListingRow,
        execution: ReviewExecution,
        status: str,
        action: str,
    ) -> None:
        sheet = self._sheet_or_none(row.sheet_name)
        if sheet is None:
            return
        review = execution.review
        columns = row.ai_columns
        values = {
            "AI Review Request": row.review_request or "AUTO",
            "AI Review Status": ("CACHED " + status) if execution.cached else status,
            "AI Action": action,
            "AI Identity Verdict": review.verdict,
            "AI Selected Candidate": review.selected_candidate_key,
            "AI Confidence %": review.confidence_percent / 100,
            "AI Edition Verdict": review.edition_verdict,
            "AI Variant Verdict": review.variant_verdict,
            "AI Listing Risk": review.listing_risk,
            "AI Risk Flags": " | ".join(review.risk_flags),
            "AI Condition Summary": review.condition_summary,
            "AI Long-Term Note": review.long_term_note,
            "AI Evidence": " | ".join(review.evidence),
            "AI Model": execution.model,
            "AI Input Tokens": execution.usage.input_tokens,
            "AI Output Tokens": execution.usage.output_tokens,
            "AI Estimated Cost ($)": 0.0 if execution.cached else execution.usage.estimated_cost_usd,
            "AI Reviewed At": datetime.now(),
            "AI Reviewed Item ID": row.item_id,
        }
        for header, value in values.items():
            sheet.Cells(row.row_number, columns[header]).Value = value
        sheet.Cells(row.row_number, columns["AI Confidence %"]).NumberFormat = "0%"
        sheet.Cells(row.row_number, columns["AI Estimated Cost ($)"]).NumberFormat = "$0.000000"
        sheet.Cells(row.row_number, columns["AI Reviewed At"]).NumberFormat = "yyyy-mm-dd hh:mm"
        colors = {
            "CONFIRMED": self.rgb(198, 239, 206),
            "REJECTED": self.rgb(255, 199, 206),
            "MANUAL REVIEW": self.rgb(255, 235, 156),
        }
        for header in ("AI Review Status", "AI Action"):
            sheet.Cells(row.row_number, columns[header]).Interior.Color = colors.get(
                status, self.rgb(221, 235, 247)
            )
        risk_colors = {
            "LOW": self.rgb(198, 239, 206),
            "MEDIUM": self.rgb(255, 235, 156),
            "HIGH": self.rgb(255, 199, 206),
            "BLOCK": self.rgb(244, 176, 132),
        }
        sheet.Cells(row.row_number, columns["AI Listing Risk"]).Interior.Color = risk_colors.get(
            review.listing_risk, self.rgb(221, 235, 247)
        )

    def append_log(
        self,
        row: ListingRow,
        execution: ReviewExecution,
        status: str,
        action: str,
    ) -> None:
        sheet = self._sheet_or_none("AI Review Log")
        if sheet is None:
            self.ensure_log_sheet()
            sheet = self._sheet_or_none("AI Review Log")
        next_row = self._last_row(sheet, 1) + 1
        review = execution.review
        values = [
            datetime.now(), row.sheet_name, row.row_number, row.item_id, row.title,
            row.current_candidate_key, review.selected_candidate_key, status, action,
            review.verdict, review.confidence_percent / 100, review.edition_verdict,
            review.variant_verdict, review.listing_risk, " | ".join(review.risk_flags),
            review.condition_summary, review.long_term_note, " | ".join(review.evidence),
            execution.model, execution.usage.input_tokens, execution.usage.output_tokens,
            0.0 if execution.cached else execution.usage.estimated_cost_usd,
            "YES" if execution.cached else "NO", execution.response_id,
        ]
        sheet.Range(
            sheet.Cells(next_row, 1), sheet.Cells(next_row, len(values))
        ).Value = (tuple(values),)
        sheet.Cells(next_row, 1).NumberFormat = "yyyy-mm-dd hh:mm"
        sheet.Cells(next_row, 11).NumberFormat = "0%"
        sheet.Cells(next_row, 22).NumberFormat = "$0.000000"
