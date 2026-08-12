from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

from long_term_investment import (
    DEFAULT_ICONIC_POKEMON,
    InvestmentContext,
    InvestmentSettings,
    PortfolioHolding,
    PriceHistoryStats,
    TargetOverride,
    apply_assessment,
    assess_candidate,
    assessment_values,
    card_key,
    normalize_text,
    pokemon_key,
)


XL_UP = -4162
XL_TO_LEFT = -4159
XL_CENTER = -4108


class LongTermWorkbookManager:
    SETTINGS_SHEET = "Investment Settings"
    TARGETS_SHEET = "Long-Term Targets"
    PORTFOLIO_SHEET = "Portfolio Vault"
    HISTORY_SHEET = "Price History"
    DASHBOARD_SHEET = "Long-Term Dashboard"

    def __init__(self, workbook) -> None:
        self.book = workbook
        self._context: InvestmentContext | None = None

    @staticmethod
    def _excel_rgb(red: int, green: int, blue: int) -> int:
        return int(red) + (int(green) << 8) + (int(blue) << 16)

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
    def _last_row(sheet, column: int = 1) -> int:
        return max(
            1,
            int(sheet.Cells(sheet.Rows.Count, column).End(XL_UP).Row),
        )

    @staticmethod
    def _clear_contents_safely(cell_range) -> None:
        """Clear an Excel range even when stale merged cells intersect it.

        Dashboard table bodies are not intended to contain merged cells.
        Older layouts or an interrupted upgrade can leave merges behind,
        causing Excel ClearContents to fail. In that case, unmerge only the
        supplied data range and retry.
        """

        try:
            cell_range.ClearContents()
            return
        except Exception:
            pass

        try:
            cell_range.UnMerge()
        except Exception:
            pass

        cell_range.ClearContents()

    def _get_or_add_sheet(self, name: str):
        try:
            return self.book.Worksheets(name), False
        except Exception:
            sheet = self.book.Worksheets.Add(
                After=self.book.Worksheets(self.book.Worksheets.Count)
            )
            sheet.Name = name
            return sheet, True

    def ensure_sheets(self) -> None:
        self._ensure_settings_sheet()
        self._ensure_targets_sheet()
        self._ensure_portfolio_sheet()
        self._ensure_history_sheet()
        self._ensure_dashboard_sheet()
        self._context = None

    def _title(self, sheet, title: str, subtitle: str, last_column: int) -> None:
        navy = self._excel_rgb(31, 78, 121)
        pale = self._excel_rgb(221, 235, 247)
        try:
            sheet.Rows(1).UnMerge()
            sheet.Rows(2).UnMerge()
        except Exception:
            pass
        sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Merge()
        sheet.Cells(1, 1).Value = title
        sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Interior.Color = navy
        sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Font.Color = self._excel_rgb(255, 255, 255)
        sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Font.Bold = True
        sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Font.Size = 16
        sheet.Rows(1).RowHeight = 28
        sheet.Range(sheet.Cells(2, 1), sheet.Cells(2, last_column)).Merge()
        sheet.Cells(2, 1).Value = subtitle
        sheet.Range(sheet.Cells(2, 1), sheet.Cells(2, last_column)).Interior.Color = pale
        sheet.Range(sheet.Cells(2, 1), sheet.Cells(2, last_column)).WrapText = True
        sheet.Rows(2).RowHeight = 34

    def _style_header(self, sheet, row: int, first: int, last: int) -> None:
        rng = sheet.Range(sheet.Cells(row, first), sheet.Cells(row, last))
        rng.Interior.Color = self._excel_rgb(31, 78, 121)
        rng.Font.Color = self._excel_rgb(255, 255, 255)
        rng.Font.Bold = True
        rng.HorizontalAlignment = XL_CENTER
        rng.WrapText = True
        sheet.Rows(row).RowHeight = 42

    def _ensure_settings_sheet(self) -> None:
        sheet, created = self._get_or_add_sheet(self.SETTINGS_SHEET)
        self._title(
            sheet,
            "Long-Term Investment Settings",
            "Blue values are editable assumptions. The 100-point score uses durable-demand, scarcity-proxy, significance, reprint-resistance, condition, price-history and entry-price components.",
            7,
        )
        labels = [
            ("Demand durability weight", 25, "Maximum points"),
            ("Scarcity proxy weight", 20, "A proxy until reliable supply/population data is added"),
            ("Card significance weight", 15, "Promo/artwork/historical-significance evidence"),
            ("Reprint resistance weight", 15, "Older/distinct releases generally score higher"),
            ("Condition investment weight", 10, "Preservation quality for a multi-year hold"),
            ("Price resilience weight", 10, "Uses accumulated Price History when available"),
            ("Acquisition discount weight", 5, "Entry price remains deliberately secondary"),
            ("Default minimum hold years", 7, "Used when no card-specific target exists"),
            ("Core Asset threshold", 90, "Score at or above"),
            ("Strong Buy threshold", 80, "Score at or above"),
            ("Selective Buy threshold", 70, "Score at or above"),
            ("Watch threshold", 60, "Score at or above"),
            ("Maximum quantity per exact card", 3, "Portfolio-fit warning threshold"),
            ("Maximum portfolio value per Pokémon (%)", 30, "Portfolio-fit concentration warning"),
        ]
        sheet.Range("A4:C17").ClearContents()
        sheet.Range("A4:C4").Value = (("Setting", "Value", "Purpose"),)
        self._style_header(sheet, 4, 1, 3)
        rows = [[label, value, purpose] for label, value, purpose in labels]
        sheet.Range("A5:C18").Value = tuple(tuple(row) for row in rows)
        sheet.Range("B5:B18").Font.Color = self._excel_rgb(0, 0, 255)
        sheet.Range("B5:B18").Interior.Color = self._excel_rgb(255, 255, 204)
        sheet.Cells(18, 2).NumberFormat = "0.0"
        sheet.Cells(20, 1).Value = "Weight total (should equal 100)"
        sheet.Cells(20, 2).Formula = "=SUM(B5:B11)"
        sheet.Cells(20, 3).Value = "Keep the seven component weights at a total of 100."
        sheet.Range("A20:C20").Font.Bold = True
        sheet.Cells(20, 2).Interior.Color = self._excel_rgb(255, 255, 0)
        for row in range(5, 19):
            cell = sheet.Cells(row, 2)
            try:
                cell.Comment.Delete()
            except Exception:
                pass
            try:
                cell.AddComment(
                    "Source: user-configurable Phase 5.5 investment-model assumption. "
                    "This is a heuristic input, not a guaranteed market fact."
                )
            except Exception:
                pass
        sheet.Columns(1).ColumnWidth = 37
        sheet.Columns(2).ColumnWidth = 14
        sheet.Columns(3).ColumnWidth = 55

        sheet.Range("E4:G4").Value = (("Iconic Pokémon", "Enabled", "Notes"),)
        self._style_header(sheet, 4, 5, 7)
        if created or self._last_row(sheet, 5) < 5:
            iconic_rows = [[name, "YES", "Editable demand-durability boost"] for name in DEFAULT_ICONIC_POKEMON]
            sheet.Range(
                sheet.Cells(5, 5),
                sheet.Cells(4 + len(iconic_rows), 7),
            ).Value = tuple(tuple(row) for row in iconic_rows)
        sheet.Range("F5:F500").Font.Color = self._excel_rgb(0, 0, 255)
        try:
            sheet.Range("F5:F500").Validation.Delete()
        except Exception:
            pass
        sheet.Range("F5:F500").Validation.Add(Type=3, AlertStyle=1, Operator=1, Formula1="YES,NO")
        sheet.Columns(5).ColumnWidth = 24
        sheet.Columns(6).ColumnWidth = 12
        sheet.Columns(7).ColumnWidth = 38
        try:
            sheet.Tab.Color = self._excel_rgb(112, 48, 160)
        except Exception:
            pass

    def _ensure_targets_sheet(self) -> None:
        sheet, _ = self._get_or_add_sheet(self.TARGETS_SHEET)
        headers = [
            "Enabled", "Card ID", "Card Name", "Set", "Card Number", "Variant",
            "Demand Override /25", "Scarcity Override /20", "Significance Override /15",
            "Reprint Override /15", "Total Score Override /100", "Desired Max Ratio",
            "Target Quantity", "Minimum Hold Years", "Thesis Override", "Risks Override",
            "Priority", "Notes",
        ]
        self._title(
            sheet,
            "Long-Term Targets and Manual Overrides",
            "Use this sheet for cards where your research is stronger than the automatic proxy. Blank override cells leave the algorithm in control.",
            len(headers),
        )
        sheet.Range(sheet.Cells(4, 1), sheet.Cells(4, len(headers))).Value = (tuple(headers),)
        self._style_header(sheet, 4, 1, len(headers))
        sheet.Range("A5:R1004").Font.Color = self._excel_rgb(0, 0, 255)
        try:
            sheet.Range("A5:A1004").Validation.Delete()
        except Exception:
            pass
        sheet.Range("A5:A1004").Validation.Add(Type=3, AlertStyle=1, Operator=1, Formula1="YES,NO")
        try:
            sheet.Range("Q5:Q1004").Validation.Delete()
        except Exception:
            pass
        sheet.Range("Q5:Q1004").Validation.Add(Type=3, AlertStyle=1, Operator=1, Formula1="CORE,HIGH,MEDIUM,LOW")
        sheet.Range("L5:L1004").NumberFormat = "0.0%"
        widths = [11, 18, 24, 24, 13, 18, 18, 18, 20, 18, 20, 17, 15, 18, 55, 55, 12, 45]
        for index, width in enumerate(widths, start=1):
            sheet.Columns(index).ColumnWidth = width
        try:
            sheet.Range("A4:R1004").AutoFilter()
            sheet.Activate()
            self.book.Application.ActiveWindow.SplitRow = 4
            self.book.Application.ActiveWindow.FreezePanes = True
        except Exception:
            pass

    def _ensure_portfolio_sheet(self) -> None:
        sheet, _ = self._get_or_add_sheet(self.PORTFOLIO_SHEET)
        headers = [
            "Purchase ID", "Card ID", "Card Name", "Set", "Card Number", "Variant",
            "Quantity", "Purchase Date", "Purchase Price (£)", "Postage & Costs (£)",
            "Total Cost (£)", "Cost / Copy (£)", "Current Market / Copy (£)",
            "Current Value (£)", "Unrealised Gain (£)", "Return %", "Long-Term Score",
            "Investment Tier", "Condition", "Raw / Graded", "Grade", "Storage Location",
            "Seller", "Minimum Hold Years", "Review Date", "Investment Thesis",
            "Investment Risks", "Action", "Status", "Notes",
        ]
        self._title(
            sheet,
            "Long-Term Portfolio Vault",
            "Record completed purchases here. Scanner runs refresh current market references, investment ratings and the dashboard; they do not generate automatic sell signals.",
            len(headers),
        )
        sheet.Range(sheet.Cells(4, 1), sheet.Cells(4, len(headers))).Value = (tuple(headers),)
        self._style_header(sheet, 4, 1, len(headers))

        # Formula-driven cost and value columns for 1,000 holdings.
        for row in range(5, 1005):
            sheet.Cells(row, 11).Formula = f"=IF(COUNTA(A{row}:J{row})=0,\"\",N(I{row})+N(J{row}))"
            sheet.Cells(row, 12).Formula = f"=IFERROR(K{row}/G{row},\"\")"
            sheet.Cells(row, 14).Formula = f"=IFERROR(M{row}*G{row},\"\")"
            sheet.Cells(row, 15).Formula = f"=IFERROR(N{row}-K{row},\"\")"
            sheet.Cells(row, 16).Formula = f"=IFERROR(O{row}/K{row},\"\")"
            sheet.Cells(row, 25).Formula = f"=IF(H{row}=\"\",\"\",EDATE(H{row},X{row}*12))"
        sheet.Range("I5:O1004").NumberFormat = '£#,##0.00;[Red](£#,##0.00);-'
        sheet.Range("P5:P1004").NumberFormat = '0.0%;[Red](0.0%);-'
        sheet.Range("H5:H1004").NumberFormat = "yyyy-mm-dd"
        sheet.Range("Y5:Y1004").NumberFormat = "yyyy-mm-dd"
        hardcoded = "A5:J1004,M5:M1004,S5:X1004,Z5:AD1004"
        for part in hardcoded.split(","):
            sheet.Range(part).Font.Color = self._excel_rgb(0, 0, 255)
        try:
            for rng, values in (
                ("T5:T1004", "RAW,GRADED"),
                ("AC5:AC1004", "OWNED,LISTED,SOLD,TRADED,ARCHIVED"),
                ("AB5:AB1004", "ACCUMULATE,HOLD,HOLD - DO NOT ADD,REVIEW THESIS,STOP BUYING,EXIT WHEN PRACTICAL"),
            ):
                sheet.Range(rng).Validation.Delete()
                sheet.Range(rng).Validation.Add(Type=3, AlertStyle=1, Operator=1, Formula1=values)
        except Exception:
            pass
        widths = [16, 18, 24, 24, 13, 18, 10, 14, 15, 17, 15, 15, 19, 16, 17, 12, 15, 24, 20, 14, 10, 20, 18, 18, 14, 55, 55, 24, 14, 45]
        for index, width in enumerate(widths, start=1):
            sheet.Columns(index).ColumnWidth = width
        try:
            sheet.Range("A4:AD1004").AutoFilter()
            sheet.Activate()
            self.book.Application.ActiveWindow.SplitRow = 4
            self.book.Application.ActiveWindow.SplitColumn = 3
            self.book.Application.ActiveWindow.FreezePanes = True
        except Exception:
            pass

    def _ensure_history_sheet(self) -> None:
        sheet, _ = self._get_or_add_sheet(self.HISTORY_SHEET)
        headers = [
            "Snapshot Date", "Source Mode", "Card ID", "Card Name", "Set", "Card Number",
            "Variant", "30-Day Average (£)", "Long-Term Score", "Investment Tier",
            "Data Confidence", "Best Observed Delivered (£)", "Best Observed Ratio",
            "Condition Flag", "Listings Observed", "Seller", "Item ID", "Snapshot Key",
        ]
        self._title(
            sheet,
            "Long-Term Price History",
            "Each scanner mode stores one daily market snapshot per card. The resilience score becomes more meaningful after at least three snapshots spanning 30 days.",
            len(headers),
        )
        sheet.Range(sheet.Cells(4, 1), sheet.Cells(4, len(headers))).Value = (tuple(headers),)
        self._style_header(sheet, 4, 1, len(headers))
        sheet.Range("A5:A200000").NumberFormat = "yyyy-mm-dd hh:mm"
        sheet.Range("H5:H200000").NumberFormat = '£#,##0.00;[Red](£#,##0.00);-'
        sheet.Range("L5:L200000").NumberFormat = '£#,##0.00;[Red](£#,##0.00);-'
        sheet.Range("M5:M200000").NumberFormat = "0.0%"
        widths = [19, 18, 18, 24, 24, 13, 18, 16, 15, 24, 15, 22, 18, 15, 17, 18, 22, 42]
        for index, width in enumerate(widths, start=1):
            sheet.Columns(index).ColumnWidth = width
        try:
            sheet.Range("A4:R200000").AutoFilter()
            sheet.Activate()
            self.book.Application.ActiveWindow.SplitRow = 4
            self.book.Application.ActiveWindow.FreezePanes = True
        except Exception:
            pass

    def _ensure_dashboard_sheet(self) -> None:
        sheet, _ = self._get_or_add_sheet(self.DASHBOARD_SHEET)
        self._title(
            sheet,
            "Long-Term Investment Dashboard",
            "Portfolio KPIs, concentration warnings and the strongest long-term opportunities found by the current scanner data.",
            12,
        )
        labels = [
            "Last refreshed", "Portfolio holdings", "Total quantity", "Total cost (£)",
            "Current value (£)", "Unrealised gain (£)", "Portfolio return", "Core assets",
            "Strong long-term buys", "Review / risk flags",
        ]
        self._clear_contents_safely(sheet.Range("A4:B14"))
        sheet.Range("A4:B4").Value = (("Portfolio KPI", "Value"),)
        self._style_header(sheet, 4, 1, 2)
        sheet.Range("A5:A14").Value = tuple((label,) for label in labels)
        sheet.Columns(1).ColumnWidth = 32
        sheet.Columns(2).ColumnWidth = 20
        sheet.Range("B8:B10").NumberFormat = '£#,##0.00;[Red](£#,##0.00);-'
        sheet.Range("B11:B11").NumberFormat = "0.0%"

        self._clear_contents_safely(sheet.Range("D4:G24"))
        self._clear_contents_safely(sheet.Range("I4:L24"))
        sheet.Range("D4:G4").Value = (("Pokémon Concentration", "Quantity", "Current Value (£)", "% of Portfolio"),)
        self._style_header(sheet, 4, 4, 7)
        sheet.Range("I4:L4").Value = (("Set Concentration", "Quantity", "Current Value (£)", "% of Portfolio"),)
        self._style_header(sheet, 4, 9, 12)
        for column in (4, 9):
            sheet.Columns(column).ColumnWidth = 27
            sheet.Columns(column + 1).ColumnWidth = 12
            sheet.Columns(column + 2).ColumnWidth = 18
            sheet.Columns(column + 3).ColumnWidth = 16
        sheet.Range("F5:F24").NumberFormat = '£#,##0.00;[Red](£#,##0.00);-'
        sheet.Range("G5:G24").NumberFormat = "0.0%"
        sheet.Range("K5:K24").NumberFormat = '£#,##0.00;[Red](£#,##0.00);-'
        sheet.Range("L5:L24").NumberFormat = "0.0%"

        try:
            sheet.Range("A17:H17").UnMerge()
        except Exception:
            pass
        sheet.Range("A17:H17").Merge()
        sheet.Cells(17, 1).Value = "Highest Long-Term Scores Seen in Recent Price History"
        sheet.Range("A17:H17").Interior.Color = self._excel_rgb(31, 78, 121)
        sheet.Range("A17:H17").Font.Color = self._excel_rgb(255, 255, 255)
        sheet.Range("A17:H17").Font.Bold = True
        sheet.Range("A18:H18").Value = (("Card", "Set", "Number", "Score", "Tier", "Market (£)", "Last Seen", "Confidence"),)
        self._style_header(sheet, 18, 1, 8)
        widths = [28, 24, 12, 10, 24, 15, 18, 14]
        for index, width in enumerate(widths, start=1):
            sheet.Columns(index).ColumnWidth = max(sheet.Columns(index).ColumnWidth, width)
        try:
            sheet.Tab.Color = self._excel_rgb(112, 48, 160)
        except Exception:
            pass

    def _setting_values(self) -> dict[str, Any]:
        try:
            sheet = self.book.Worksheets(self.SETTINGS_SHEET)
        except Exception:
            return {}
        output = {}
        for row in range(5, 19):
            key = str(sheet.Cells(row, 1).Value or "").strip()
            if key:
                output[key] = sheet.Cells(row, 2).Value
        return output

    @staticmethod
    def _number(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def read_settings(self) -> InvestmentSettings:
        values = self._setting_values()
        iconic: list[str] = []
        try:
            sheet = self.book.Worksheets(self.SETTINGS_SHEET)
            last = self._last_row(sheet, 5)
            for row in range(5, last + 1):
                name = str(sheet.Cells(row, 5).Value or "").strip()
                enabled = str(sheet.Cells(row, 6).Value or "YES").strip().upper()
                if name and enabled != "NO":
                    iconic.append(name)
        except Exception:
            pass
        return InvestmentSettings(
            demand_weight=int(self._number(values.get("Demand durability weight"), 25)),
            scarcity_weight=int(self._number(values.get("Scarcity proxy weight"), 20)),
            significance_weight=int(self._number(values.get("Card significance weight"), 15)),
            reprint_weight=int(self._number(values.get("Reprint resistance weight"), 15)),
            condition_weight=int(self._number(values.get("Condition investment weight"), 10)),
            resilience_weight=int(self._number(values.get("Price resilience weight"), 10)),
            acquisition_weight=int(self._number(values.get("Acquisition discount weight"), 5)),
            default_hold_years=int(self._number(values.get("Default minimum hold years"), 7)),
            core_asset_threshold=int(self._number(values.get("Core Asset threshold"), 90)),
            strong_buy_threshold=int(self._number(values.get("Strong Buy threshold"), 80)),
            selective_buy_threshold=int(self._number(values.get("Selective Buy threshold"), 70)),
            watch_threshold=int(self._number(values.get("Watch threshold"), 60)),
            max_same_card_quantity=int(self._number(values.get("Maximum quantity per exact card"), 3)),
            max_same_pokemon_percent=self._number(values.get("Maximum portfolio value per Pokémon (%)"), 30),
            iconic_pokemon=tuple(iconic or DEFAULT_ICONIC_POKEMON),
        )

    def read_overrides(self) -> dict[str, TargetOverride]:
        output: dict[str, TargetOverride] = {}
        try:
            sheet = self.book.Worksheets(self.TARGETS_SHEET)
        except Exception:
            return output
        last = self._last_row(sheet, 2)
        if last < 5:
            return output
        rows = self._rows(sheet.Range(f"A5:R{last}").Value)
        for row in rows:
            enabled = str(row[0] or "YES").strip().upper() != "NO"
            card_id = str(row[1] or "").strip()
            name = str(row[2] or "").strip()
            set_name = str(row[3] or "").strip()
            number = str(row[4] or "").strip()
            variant = str(row[5] or "").strip()
            if not card_id and not name:
                continue
            def optional_number(index: int) -> float | None:
                try:
                    return float(row[index]) if row[index] not in (None, "") else None
                except (TypeError, ValueError):
                    return None
            override = TargetOverride(
                enabled=enabled,
                card_id=card_id,
                name=name,
                set_name=set_name,
                number=number,
                variant=variant,
                demand_score=optional_number(6),
                scarcity_score=optional_number(7),
                significance_score=optional_number(8),
                reprint_score=optional_number(9),
                total_score=optional_number(10),
                desired_max_ratio=optional_number(11),
                target_quantity=int(optional_number(12)) if optional_number(12) is not None else None,
                minimum_hold_years=int(optional_number(13)) if optional_number(13) is not None else None,
                thesis=str(row[14] or ""),
                risks=str(row[15] or ""),
                priority=str(row[16] or ""),
                notes=str(row[17] or ""),
            )
            keys = []
            if card_id:
                keys.append(card_id.casefold())
            keys.append("|".join(normalize_text(value) for value in (name, set_name, number, variant)))
            keys.append("|".join(normalize_text(value) for value in (name, number)))
            for key in keys:
                if key.strip("|"):
                    output[key] = override
        return output

    def read_history(self) -> dict[str, PriceHistoryStats]:
        output: dict[str, PriceHistoryStats] = defaultdict(PriceHistoryStats)
        try:
            sheet = self.book.Worksheets(self.HISTORY_SHEET)
        except Exception:
            return {}
        last = self._last_row(sheet, 1)
        if last < 5:
            return {}
        rows = self._rows(sheet.Range(f"A5:H{last}").Value)
        for row in rows:
            timestamp = row[0]
            card_id = str(row[2] or "").strip()
            name = str(row[3] or "").strip()
            set_name = str(row[4] or "").strip()
            number = str(row[5] or "").strip()
            variant = str(row[6] or "").strip()
            try:
                market = float(row[7] or 0)
            except (TypeError, ValueError):
                continue
            if market <= 0:
                continue
            if not isinstance(timestamp, datetime):
                continue
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            key = card_id.casefold() if card_id else "|".join(normalize_text(value) for value in (name, set_name, number, variant))
            output[key].values.append((timestamp, market))
        return dict(output)

    def read_portfolio(self) -> tuple[dict[str, PortfolioHolding], dict[str, PortfolioHolding], float]:
        by_card: dict[str, PortfolioHolding] = {}
        by_pokemon: dict[str, PortfolioHolding] = {}
        total_value = 0.0
        try:
            sheet = self.book.Worksheets(self.PORTFOLIO_SHEET)
        except Exception:
            return by_card, by_pokemon, total_value
        last = self._last_row(sheet, 1)
        if last < 5:
            return by_card, by_pokemon, total_value
        rows = self._rows(sheet.Range(f"A5:AC{last}").Value)
        for row in rows:
            status = str(row[28] or "OWNED").strip().upper()
            if status in {"SOLD", "TRADED", "ARCHIVED"}:
                continue
            candidate = SimpleNamespace(
                card_id=str(row[1] or ""),
                name=str(row[2] or ""),
                set_name=str(row[3] or ""),
                number=str(row[4] or ""),
                variant=str(row[5] or ""),
            )
            if not candidate.card_id and not candidate.name:
                continue
            try:
                quantity = max(1, int(row[6] or 1))
            except (TypeError, ValueError):
                quantity = 1
            try:
                cost = float(row[10] or 0)
            except (TypeError, ValueError):
                cost = 0.0
            try:
                current_value = float(row[13] or 0)
            except (TypeError, ValueError):
                current_value = 0.0
            key = card_key(candidate)
            pkey = pokemon_key(candidate.name)
            old = by_card.get(key)
            by_card[key] = PortfolioHolding(
                key,
                pkey,
                quantity + (old.quantity if old else 0),
                cost + (old.cost if old else 0),
                current_value + (old.current_value if old else 0),
            )
            old_p = by_pokemon.get(pkey)
            by_pokemon[pkey] = PortfolioHolding(
                pkey,
                pkey,
                quantity + (old_p.quantity if old_p else 0),
                cost + (old_p.cost if old_p else 0),
                current_value + (old_p.current_value if old_p else 0),
            )
            total_value += current_value
        return by_card, by_pokemon, total_value

    def context(self, refresh: bool = False) -> InvestmentContext:
        if self._context is None or refresh:
            settings = self.read_settings()
            by_card, by_pokemon, total = self.read_portfolio()
            self._context = InvestmentContext(
                settings=settings,
                overrides=self.read_overrides(),
                history=self.read_history(),
                portfolio_by_card=by_card,
                portfolio_by_pokemon=by_pokemon,
                total_portfolio_value=total,
            )
        return self._context

    def assess_candidate(self, candidate: Any, *, ratio: float | None = None, condition_flag: Any = "UNKNOWN", condition_details: Any = ""):
        return assess_candidate(
            candidate,
            self.context(),
            ratio=ratio,
            condition_flag=condition_flag,
            condition_details=condition_details,
        )

    def assess_results(self, results: Iterable[Any]) -> None:
        context = self.context()
        for result in results:
            assessment = assess_candidate(
                result.candidate,
                context,
                ratio=getattr(result, "ratio", None),
                condition_flag=getattr(result, "condition_flag", "UNKNOWN"),
                condition_details=(
                    str(getattr(result, "condition", "") or "")
                    + " "
                    + str(getattr(result, "condition_details", "") or "")
                ).strip(),
            )
            apply_assessment(result, assessment)

    def append_price_history(self, mode: str, results: Iterable[Any]) -> int:
        try:
            sheet = self.book.Worksheets(self.HISTORY_SHEET)
        except Exception:
            return 0
        mode = str(mode or "UNKNOWN").strip().upper()
        today = datetime.now().strftime("%Y-%m-%d")
        last = self._last_row(sheet, 1)
        existing: set[str] = set()
        if last >= 5:
            for row in self._rows(sheet.Range(f"R5:R{last}").Value):
                key = str(row[0] or "").strip()
                if key:
                    existing.add(key)

        grouped: dict[str, list[Any]] = defaultdict(list)
        for result in results:
            grouped[card_key(result.candidate)].append(result)

        rows = []
        for key, group in grouped.items():
            first = group[0]
            snapshot_key = f"{today}|{mode}|{key}"
            if snapshot_key in existing:
                continue
            delivered_values = [
                value
                for value in (getattr(item, "delivered", None) for item in group)
                if isinstance(value, (int, float))
            ]
            ratio_values = [
                value
                for value in (getattr(item, "ratio", None) for item in group)
                if isinstance(value, (int, float))
            ]
            rows.append([
                datetime.now(),
                mode,
                getattr(first.candidate, "card_id", ""),
                getattr(first.candidate, "name", ""),
                getattr(first.candidate, "set_name", ""),
                getattr(first.candidate, "number", ""),
                getattr(first.candidate, "variant", ""),
                getattr(first.candidate, "market_value", 0),
                getattr(first, "long_term_score", 0),
                getattr(first, "investment_tier", ""),
                getattr(first, "investment_data_confidence", ""),
                min(delivered_values) if delivered_values else None,
                min(ratio_values) if ratio_values else None,
                getattr(first, "condition_flag", ""),
                len(group),
                getattr(first, "seller", ""),
                getattr(first, "item_id", ""),
                snapshot_key,
            ])

        if not rows:
            return 0
        start = max(5, last + 1)
        bottom = start + len(rows) - 1
        sheet.Range(sheet.Cells(start, 1), sheet.Cells(bottom, 18)).Value = tuple(tuple(row) for row in rows)
        return len(rows)

    def refresh_portfolio(self, candidates: Iterable[Any]) -> int:
        try:
            sheet = self.book.Worksheets(self.PORTFOLIO_SHEET)
        except Exception:
            return 0
        candidate_map: dict[str, Any] = {}
        loose_map: dict[str, Any] = {}
        for candidate in candidates:
            candidate_map[card_key(candidate)] = candidate
            loose_map["|".join(normalize_text(value) for value in (getattr(candidate, "name", ""), getattr(candidate, "set_name", ""), getattr(candidate, "number", "")))] = candidate
        last = self._last_row(sheet, 1)
        if last < 5:
            return 0
        updated = 0
        context = self.context(refresh=True)
        for row in range(5, last + 1):
            card_id = str(sheet.Cells(row, 2).Value or "").strip()
            name = str(sheet.Cells(row, 3).Value or "").strip()
            set_name = str(sheet.Cells(row, 4).Value or "").strip()
            number = str(sheet.Cells(row, 5).Value or "").strip()
            variant = str(sheet.Cells(row, 6).Value or "").strip()
            if not card_id and not name:
                continue
            key = card_id.casefold() if card_id else "|".join(normalize_text(value) for value in (name, set_name, number, variant))
            candidate = candidate_map.get(key) or loose_map.get("|".join(normalize_text(value) for value in (name, set_name, number)))
            if candidate is None:
                continue
            live_value = float(getattr(candidate, "market_value", 0) or 0)
            if live_value <= 0:
                # Do not erase an existing portfolio valuation merely because
                # that card was not encountered and priced during this scan.
                continue
            sheet.Cells(row, 13).Value = live_value
            condition = str(sheet.Cells(row, 19).Value or "")
            assessment = assess_candidate(candidate, context, condition_flag="UNKNOWN", condition_details=condition)
            sheet.Cells(row, 17).Value = assessment.long_term_score
            sheet.Cells(row, 18).Value = assessment.investment_tier
            if not str(sheet.Cells(row, 24).Value or "").strip():
                sheet.Cells(row, 24).Value = assessment.minimum_hold_years
            if not str(sheet.Cells(row, 26).Value or "").strip():
                sheet.Cells(row, 26).Value = assessment.thesis
            if not str(sheet.Cells(row, 27).Value or "").strip():
                sheet.Cells(row, 27).Value = assessment.risks
            sheet.Cells(row, 28).Value = assessment.long_term_action
            updated += 1
        self._context = None
        return updated

    def refresh_dashboard(self) -> None:
        try:
            dashboard = self.book.Worksheets(self.DASHBOARD_SHEET)
            portfolio = self.book.Worksheets(self.PORTFOLIO_SHEET)
            history = self.book.Worksheets(self.HISTORY_SHEET)
        except Exception:
            return
        last = self._last_row(portfolio, 1)
        holdings = []
        if last >= 5:
            holdings = self._rows(portfolio.Range(f"A5:AC{last}").Value)
        active = [row for row in holdings if (row[0] or row[1] or row[2]) and str(row[28] or "OWNED").strip().upper() not in {"SOLD", "TRADED", "ARCHIVED"}]
        total_quantity = 0
        total_cost = 0.0
        total_value = 0.0
        core = 0
        strong = 0
        risk_flags = 0
        pokemon_summary: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        set_summary: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for row in active:
            try:
                quantity = max(1, int(row[6] or 1))
            except (TypeError, ValueError):
                quantity = 1
            try:
                cost = float(row[10] or 0)
            except (TypeError, ValueError):
                cost = 0.0
            try:
                value = float(row[13] or 0)
            except (TypeError, ValueError):
                value = 0.0
            tier = str(row[17] or "")
            action = str(row[27] or "")
            total_quantity += quantity
            total_cost += cost
            total_value += value
            core += tier == "CORE ASSET"
            strong += tier == "STRONG LONG-TERM BUY"
            risk_flags += any(token in action for token in ("REVIEW", "STOP", "EXIT", "DO NOT ADD"))
            pkey = pokemon_key(row[2])
            skey = str(row[3] or "Unknown Set")
            pokemon_summary[pkey][0] += quantity
            pokemon_summary[pkey][1] += value
            set_summary[skey][0] += quantity
            set_summary[skey][1] += value

        values = [
            datetime.now(), len(active), total_quantity, total_cost, total_value,
            total_value - total_cost, ((total_value - total_cost) / total_cost if total_cost else 0),
            core, strong, risk_flags,
        ]
        dashboard.Range("B5:B14").Value = tuple((value,) for value in values)
        self._clear_contents_safely(dashboard.Range("D5:G24"))
        self._clear_contents_safely(dashboard.Range("I5:L24"))
        pokemon_rows = sorted(pokemon_summary.items(), key=lambda item: item[1][1], reverse=True)[:20]
        set_rows = sorted(set_summary.items(), key=lambda item: item[1][1], reverse=True)[:20]
        if pokemon_rows:
            rows = [[name.title(), int(data[0]), data[1], data[1] / total_value if total_value else 0] for name, data in pokemon_rows]
            dashboard.Range(dashboard.Cells(5, 4), dashboard.Cells(4 + len(rows), 7)).Value = tuple(tuple(row) for row in rows)
        if set_rows:
            rows = [[name, int(data[0]), data[1], data[1] / total_value if total_value else 0] for name, data in set_rows]
            dashboard.Range(dashboard.Cells(5, 9), dashboard.Cells(4 + len(rows), 12)).Value = tuple(tuple(row) for row in rows)

        history_last = self._last_row(history, 1)
        self._clear_contents_safely(dashboard.Range("A19:H68"))
        if history_last >= 5:
            rows = self._rows(history.Range(f"A5:K{history_last}").Value)
            latest_by_card: dict[str, tuple[Any, ...]] = {}
            for row in rows:
                key = str(row[2] or "") or "|".join(str(value or "") for value in row[3:7])
                old = latest_by_card.get(key)
                if old is None or (isinstance(row[0], datetime) and isinstance(old[0], datetime) and row[0] > old[0]):
                    latest_by_card[key] = row
            top = sorted(latest_by_card.values(), key=lambda row: float(row[8] or 0), reverse=True)[:50]
            if top:
                output = [[row[3], row[4], row[5], row[8], row[9], row[7], row[0], row[10]] for row in top]
                dashboard.Range(dashboard.Cells(19, 1), dashboard.Cells(18 + len(output), 8)).Value = tuple(tuple(row) for row in output)
                dashboard.Range(f"F19:F{18 + len(output)}").NumberFormat = '£#,##0.00;[Red](£#,##0.00);-'
                dashboard.Range(f"G19:G{18 + len(output)}").NumberFormat = "yyyy-mm-dd"

    def update_after_scan(self, mode: str, results: Iterable[Any], candidates: Iterable[Any]) -> dict[str, int]:
        results = list(results)
        snapshots = self.append_price_history(mode, results)
        portfolio = self.refresh_portfolio(candidates)
        self.refresh_dashboard()
        self._context = None
        return {"snapshots": snapshots, "portfolio_rows": portfolio}
