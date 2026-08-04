from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .core import Candidate, ListingResult, Settings
from .core import (
    parse_cooldown_days,
    parse_currency_or_any,
    parse_duration_hours,
    parse_percentage,
    normalize_card_number,
)


XL_UP = -4162
XL_TO_LEFT = -4159


class ExcelAdapter:
    def __init__(self, workbook_path: Path, visible: bool = False) -> None:
        import win32com.client

        self.workbook_path = workbook_path
        self.excel = win32com.client.DispatchEx("Excel.Application")
        self.excel.Visible = visible
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
            int(sheet.Cells(sheet.Rows.Count, column).End(XL_UP).Row),
        )

    @staticmethod
    def _as_rows(value: Any) -> list[tuple[Any, ...]]:
        if value is None:
            return []
        if isinstance(value, tuple):
            if value and isinstance(value[0], tuple):
                return list(value)
            return [value]
        return [(value,)]

    @staticmethod
    def _excel_rgb(red: int, green: int, blue: int) -> int:
        return int(red) + (int(green) << 8) + (int(blue) << 16)

    def _style_decision_cell(self, cell, decision: str) -> None:
        decision = str(decision or "").strip().upper()
        palette = {
            "GREEN": ((198, 239, 206), (0, 97, 0)),
            "AMBER": ((255, 235, 156), (156, 101, 0)),
            "RED": ((255, 199, 206), (156, 0, 6)),
            "N/A": ((217, 217, 217), (89, 89, 89)),
        }
        fill, font = palette.get(decision, ((255, 255, 255), (0, 0, 0)))
        cell.Interior.Color = self._excel_rgb(*fill)
        cell.Font.Color = self._excel_rgb(*font)
        cell.Font.Bold = True
        cell.HorizontalAlignment = -4108

    def _style_result_decisions(
        self,
        sheet,
        start_row: int,
        results: list[ListingResult],
        overall_column: int,
        bid_column: int,
        buy_now_column: int,
    ) -> None:
        for offset, result in enumerate(results):
            row = start_row + offset
            self._style_decision_cell(
                sheet.Cells(row, overall_column),
                result.decision,
            )
            self._style_decision_cell(
                sheet.Cells(row, bid_column),
                result.bid_decision,
            )
            self._style_decision_cell(
                sheet.Cells(row, buy_now_column),
                result.buy_now_decision,
            )

    def read_settings(self) -> Settings:
        sheet = self.sheet("Random Range Sniper")
        values = {
            str(sheet.Cells(row, 1).Value or "").strip():
            sheet.Cells(row, 2).Value
            for row in range(4, 22)
        }

        return Settings(
            minimum_value=float(values.get("Minimum market value (£)") or 5),
            maximum_value=float(values.get("Maximum market value (£)") or 40),
            number_of_cards=int(values.get("Number of cards") or 20),
            selection_mode=str(
                values.get("Selection mode") or "Smart Random"
            ),
            category=str(values.get("Card category") or "Pokémon only"),
            variant_filter=str(
                values.get("Variant selection") or "Any"
            ),
            one_variant_per_card=str(
                values.get("One variant per card") or "YES"
            ).upper() == "YES",
            cooldown_days=parse_cooldown_days(
                values.get("Avoid recent repeats")
            ),
            replace_no_results=str(
                values.get("Replace cards with no auctions") or "YES"
            ).upper() == "YES",
            search_depth=str(values.get("Search depth") or "Balanced"),
            target_ratio=parse_percentage(
                values.get("Target purchase ratio"),
                0.75,
            ),
            ending_within_hours=parse_duration_hours(
                values.get("Ending within"),
                24,
            ),
            minimum_feedback=parse_percentage(
                values.get("Minimum seller feedback"),
                0.98,
            ) * 100,
            maximum_postage=parse_currency_or_any(
                values.get("Maximum postage")
            ),
            copy_green_to_main_queue=str(
                values.get("Copy GREEN to Snipe Queue") or "YES"
            ).upper() == "YES",
            maximum_attempts=int(
                values.get("Maximum card attempts") or 60
            ),
            random_seed=str(values.get("Random seed") or "").strip(),
            listing_formats=str(
                values.get("Listing formats") or "Auctions + Buy It Now"
            ),
        )

    def read_full_database(self) -> dict[tuple[str, str, str], dict[str, Any]]:
        sheet = self.sheet("Full Card Database")
        last_row = self._last_row(sheet, 1)
        if last_row < 5:
            return {}

        values = self._as_rows(
            sheet.Range(f"A5:AF{last_row}").Value
        )
        output: dict[tuple[str, str, str], dict[str, Any]] = {}

        for row in values:
            name = str(row[1] or "").strip()
            set_name = str(row[3] or "").strip()
            number = normalize_card_number(row[5])
            key = (
                name.casefold(),
                set_name.casefold(),
                number.casefold(),
            )
            output[key] = {
                "card_id": str(row[0] or "").strip(),
                "rarity": str(row[7] or "").strip(),
                "supertype": str(row[8] or "").strip(),
                "release_date": row[13],
                "image_url": str(row[29] or "").strip(),
            }
        return output

    def read_price_changes(self) -> dict[tuple[str, str, str, str], float]:
        try:
            sheet = self.sheet("Market Price Changes")
        except Exception:
            return {}

        last_row = self._last_row(sheet, 1)
        if last_row < 5:
            return {}

        values = self._as_rows(
            sheet.Range(f"B5:J{last_row}").Value
        )
        output: dict[tuple[str, str, str, str], float] = {}

        for row in values:
            # B:J -> card id, name, set, number, variant, previous,
            # current, change, percent.
            name = str(row[1] or "").strip()
            set_name = str(row[2] or "").strip()
            number = normalize_card_number(row[3])
            variant = str(row[4] or "").strip()
            try:
                change = float(row[7] or 0)
            except (TypeError, ValueError):
                change = 0.0
            output[
                (
                    name.casefold(),
                    set_name.casefold(),
                    number.casefold(),
                    variant.casefold(),
                )
            ] = change
        return output

    def read_history_stats(
        self,
    ) -> tuple[
        dict[str, int],
        dict[str, int],
        dict[str, datetime],
    ]:
        sheet = self.sheet("Random Snipe History")
        last_row = self._last_row(sheet, 1)
        if last_row < 5:
            return {}, {}, {}

        values = self._as_rows(
            sheet.Range(f"B5:Q{last_row}").Value
        )
        scans: dict[str, int] = defaultdict(int)
        green: dict[str, int] = defaultdict(int)
        last_selected: dict[str, datetime] = {}

        for row in values:
            timestamp = row[0]
            card_id = str(row[2] or "").strip()
            name = str(row[3] or "").strip()
            set_name = str(row[4] or "").strip()
            number = normalize_card_number(row[5])
            variant = str(row[6] or "").strip()
            identity = (
                f"{card_id or f'{name}|{set_name}|{number}'}|{variant}"
            ).casefold()
            scans[identity] += 1
            try:
                green[identity] += int(row[14] or 0)
            except (TypeError, ValueError):
                pass

            if isinstance(timestamp, datetime):
                aware = timestamp
                if aware.tzinfo is None:
                    aware = aware.replace(tzinfo=timezone.utc)
                old = last_selected.get(identity)
                if old is None or aware > old:
                    last_selected[identity] = aware

        return dict(scans), dict(green), last_selected

    def read_candidates(self) -> list[Candidate]:
        database = self.read_full_database()
        changes = self.read_price_changes()
        scans, green, selected_dates = self.read_history_stats()

        sheet = self.sheet("Market Data Import")
        last_row = self._last_row(sheet, 1)
        values = self._as_rows(
            sheet.Range(f"A5:L{last_row}").Value
        )

        output: list[Candidate] = []
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

            key = (
                name.casefold(),
                set_name.casefold(),
                number.casefold(),
            )
            details = database.get(key, {})
            card_id = str(details.get("card_id", "") or "")
            identity = (
                f"{card_id or f'{name}|{set_name}|{number}'}|{variant}"
            ).casefold()

            output.append(
                Candidate(
                    card_id=card_id,
                    name=name,
                    set_name=set_name,
                    number=number,
                    variant=variant,
                    market_value=market_value,
                    source=str(row[8] or ""),
                    source_date=row[9],
                    source_url=str(row[10] or ""),
                    rarity=str(details.get("rarity", "") or ""),
                    supertype=str(details.get("supertype", "") or ""),
                    release_date=details.get("release_date"),
                    image_url=str(details.get("image_url", "") or ""),
                    price_change=changes.get(
                        (
                            name.casefold(),
                            set_name.casefold(),
                            number.casefold(),
                            variant.casefold(),
                        ),
                        0.0,
                    ),
                    historical_scans=scans.get(identity, 0),
                    historical_green=green.get(identity, 0),
                    last_selected=selected_dates.get(identity),
                )
            )

        return output

    def clear_selected_rows(self) -> None:
        sheet = self.sheet("Random Range Sniper")
        sheet.Range("A24:V273").ClearContents()
        try:
            sheet.Range("M24:O273").Hyperlinks.Delete()
        except Exception:
            pass

    def write_selected_cards(
        self,
        attempts: list[dict[str, Any]],
    ) -> None:
        sheet = self.sheet("Random Range Sniper")
        sheet.Range("A24:W273").ClearContents()
        try:
            sheet.Range("M24:P273").Hyperlinks.Delete()
        except Exception:
            pass

        rows = []
        for index, attempt in enumerate(attempts, start=1):
            candidate: Candidate = attempt["candidate"]
            result_count = int(attempt.get("listings_found", 0))
            best = attempt.get("best_result")
            best_delivered = best.delivered if best else None
            best_discount = (
                1 - best.ratio
                if best and best.market_value
                else None
            )
            best_decision = best.decision if best else ""
            best_action = best.recommended_action if best else ""
            rows.append(
                [
                    index,
                    attempt.get("status", "SELECTED"),
                    candidate.card_id,
                    candidate.name,
                    candidate.set_name,
                    candidate.number,
                    candidate.variant,
                    candidate.rarity,
                    candidate.market_value,
                    candidate.market_value * attempt["target_ratio"],
                    candidate.source,
                    candidate.source_date,
                    "Open Card Image" if candidate.image_url else "",
                    "Open Auction Search",
                    "Open Buy Now Search",
                    "Open Sold Results",
                    int(attempt.get("queries_run", 0)),
                    result_count,
                    best_delivered,
                    best_discount,
                    best_decision,
                    best_action,
                    datetime.now(),
                    attempt.get("notes", ""),
                ]
            )

        if rows:
            bottom = 23 + len(rows)
            sheet.Range(
                sheet.Cells(24, 1),
                sheet.Cells(bottom, 24),
            ).Value = tuple(tuple(row) for row in rows)

            for offset, attempt in enumerate(attempts):
                row = 24 + offset
                candidate: Candidate = attempt["candidate"]
                if candidate.image_url:
                    sheet.Hyperlinks.Add(
                        Anchor=sheet.Cells(row, 13),
                        Address=candidate.image_url,
                        TextToDisplay="Open Card Image",
                    )
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 14),
                    Address=attempt["active_search_url"],
                    TextToDisplay="Open Auction Search",
                )
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 15),
                    Address=attempt["buy_now_search_url"],
                    TextToDisplay="Open Buy Now Search",
                )
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 16),
                    Address=attempt["sold_search_url"],
                    TextToDisplay="Open Sold Results",
                )
                if best := attempt.get("best_result"):
                    self._style_decision_cell(
                        sheet.Cells(row, 21),
                        best.decision,
                    )

    @staticmethod
    def _result_row(order: int, result: ListingResult) -> list[Any]:
        card_label = (
            f"{result.candidate.name} | "
            f"{result.candidate.set_name} | "
            f"{result.candidate.number} | "
            f"{result.candidate.variant}"
        )
        return [
            order,
            result.decision,
            result.recommended_action,
            result.score,
            result.listing_type,
            card_label,
            result.candidate.card_id,
            result.candidate.set_name,
            result.candidate.number,
            result.candidate.variant,
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
            result.target_delivered,
            result.maximum_bid,
            result.bid_headroom,
            result.buy_now_headroom,
            result.bid_decision,
            result.buy_now_decision,
            result.end_time.replace(tzinfo=None),
            result.minutes_remaining,
            result.bid_count,
            result.seller,
            result.feedback_percent / 100,
            result.feedback_count,
            result.condition,
            result.match_confidence,
            result.search_query,
            "Open Listing",
            "Open Auction Search",
            "Open Buy Now Search",
            "Open Sold Results",
            "Open Card Image" if result.candidate.image_url else "",
            "NEW",
            result.notes,
        ]

    def _write_result_sheet(
        self,
        sheet_name: str,
        results: list[ListingResult],
    ) -> None:
        sheet = self.sheet(sheet_name)
        sheet.Range("A5:AP1504").ClearContents()
        try:
            sheet.Range("AJ5:AN1504").Hyperlinks.Delete()
        except Exception:
            pass

        rows = [
            self._result_row(order, result)
            for order, result in enumerate(results, start=1)
        ]
        if not rows:
            return

        bottom = 4 + len(rows)
        sheet.Range(
            sheet.Cells(5, 1),
            sheet.Cells(bottom, 42),
        ).Value = tuple(tuple(row) for row in rows)

        self._style_result_decisions(
            sheet,
            5,
            results,
            overall_column=2,
            bid_column=25,
            buy_now_column=26,
        )

        for offset, result in enumerate(results):
            row = 5 + offset
            sheet.Hyperlinks.Add(
                Anchor=sheet.Cells(row, 36),
                Address=result.item_url,
                TextToDisplay="Open Listing",
            )
            sheet.Hyperlinks.Add(
                Anchor=sheet.Cells(row, 37),
                Address=result.auction_search_url,
                TextToDisplay="Open Auction Search",
            )
            sheet.Hyperlinks.Add(
                Anchor=sheet.Cells(row, 38),
                Address=result.buy_now_search_url,
                TextToDisplay="Open Buy Now Search",
            )
            sheet.Hyperlinks.Add(
                Anchor=sheet.Cells(row, 39),
                Address=result.sold_search_url,
                TextToDisplay="Open Sold Results",
            )
            if result.candidate.image_url:
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 40),
                    Address=result.candidate.image_url,
                    TextToDisplay="Open Card Image",
                )

    def write_results(self, results: list[ListingResult]) -> None:
        self._write_result_sheet("Random Snipe Results", results)

    def write_random_snipe_queue(
        self,
        results: list[ListingResult],
    ) -> None:
        self._write_result_sheet("Random Snipe Queue", results)

    def append_history(
        self,
        run_id: str,
        settings: Settings,
        attempts: list[dict[str, Any]],
    ) -> None:
        sheet = self.sheet("Random Snipe History")
        start_row = max(5, self._last_row(sheet, 1) + 1)
        timestamp = datetime.now()

        rows = []
        for order, attempt in enumerate(attempts, start=1):
            candidate: Candidate = attempt["candidate"]
            results: list[ListingResult] = attempt.get("results", [])
            best = min(
                results,
                key=lambda item: item.ratio,
                default=None,
            )
            green = sum(item.decision == "GREEN" for item in results)
            amber = sum(item.decision == "AMBER" for item in results)
            red = sum(item.decision == "RED" for item in results)
            rows.append(
                [
                    run_id,
                    timestamp,
                    order,
                    candidate.card_id,
                    candidate.name,
                    candidate.set_name,
                    candidate.number,
                    candidate.variant,
                    candidate.market_value,
                    settings.selection_mode,
                    settings.minimum_value,
                    settings.maximum_value,
                    settings.search_depth,
                    int(attempt.get("queries_run", 0)),
                    len(results),
                    green,
                    amber,
                    red,
                    best.delivered if best else None,
                    (1 - best.ratio) if best else None,
                    attempt.get("status", ""),
                    attempt["active_search_url"],
                    attempt["sold_search_url"],
                ]
            )

        if rows:
            bottom = start_row + len(rows) - 1
            sheet.Range(
                sheet.Cells(start_row, 1),
                sheet.Cells(bottom, 23),
            ).Value = tuple(tuple(row) for row in rows)

            for offset, attempt in enumerate(attempts):
                row = start_row + offset
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 22),
                    Address=attempt["active_search_url"],
                    TextToDisplay="Open Active Search",
                )
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 23),
                    Address=attempt["sold_search_url"],
                    TextToDisplay="Open Sold Results",
                )

    def update_kpis(
        self,
        run_id: str,
        eligible_pool: int,
        attempts: list[dict[str, Any]],
        results: list[ListingResult],
        queue_results: list[ListingResult],
        api_calls: int,
        mode: str,
    ) -> None:
        sheet = self.sheet("Random Range Sniper")
        values = [
            [datetime.now()],
            [run_id],
            [mode],
            [eligible_pool],
            [len(attempts)],
            [
                sum(
                    int(attempt.get("listings_found", 0)) > 0
                    for attempt in attempts
                )
            ],
            [len(results)],
            [len(queue_results)],
            [sum(result.decision == "GREEN" for result in queue_results)],
            [sum(result.decision == "AMBER" for result in queue_results)],
            [api_calls],
            ["SUCCESS"],
        ]
        sheet.Range("E4:E15").Value = tuple(tuple(row) for row in values)

    def copy_green_to_snipe_queue(
        self,
        results: list[ListingResult],
    ) -> int:
        # The legacy Snipe Queue is auction-shaped, so copy only GREEN auction
        # scenarios. Buy It Now opportunities remain in Random Snipe Queue.
        green = [
            result for result in results
            if result.bid_decision == "GREEN"
            and result.current_bid is not None
        ]
        if not green:
            return 0

        sheet = self.sheet("Snipe Queue")
        sheet.Range("A5:AA505").ClearContents()
        try:
            sheet.Range("X5:Y505").Hyperlinks.Delete()
        except Exception:
            pass

        rows = []
        for priority, result in enumerate(green[:500], start=1):
            card_label = (
                f"{result.candidate.name} | "
                f"{result.candidate.set_name} | "
                f"{result.candidate.number} | "
                f"{result.candidate.variant}"
            )
            rows.append(
                [
                    priority,
                    result.bid_decision,
                    result.score,
                    card_label,
                    result.title,
                    result.item_id,
                    result.current_bid,
                    result.postage,
                    result.bid_delivered,
                    result.market_value,
                    result.bid_ratio,
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
                    result.match_confidence,
                    f"Random Range: {result.search_query}",
                    "Open Listing",
                    (
                        "Open Card Image"
                        if result.candidate.image_url
                        else ""
                    ),
                ]
            )

        bottom = 4 + len(rows)
        sheet.Range(
            sheet.Cells(5, 1),
            sheet.Cells(bottom, 25),
        ).Value = tuple(tuple(row) for row in rows)

        for offset, result in enumerate(green[:500]):
            row = 5 + offset
            self._style_decision_cell(sheet.Cells(row, 2), "GREEN")
            sheet.Hyperlinks.Add(
                Anchor=sheet.Cells(row, 24),
                Address=result.item_url,
                TextToDisplay="Open Listing",
            )
            if result.candidate.image_url:
                sheet.Hyperlinks.Add(
                    Anchor=sheet.Cells(row, 25),
                    Address=result.candidate.image_url,
                    TextToDisplay="Open Card Image",
                )
        return len(rows)

