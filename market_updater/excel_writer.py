from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .pricing import FxRates, PriceVariant, best_price_summary
from market_price_controls import (
    ensure_controls_sheet,
    mark_controls_applied,
    read_controls,
    resolve_effective_value,
)


XL_UP = -4162
XL_TO_LEFT = -4159
XL_DATABASE = 1


def _get_or_add_sheet(workbook, name: str):
    try:
        return workbook.Worksheets(name)
    except Exception:
        sheet = workbook.Worksheets.Add(After=workbook.Worksheets(workbook.Worksheets.Count))
        sheet.Name = name
        return sheet


def _last_used_row(sheet, column: int = 1) -> int:
    try:
        return max(1, int(sheet.Cells(sheet.Rows.Count, column).End(XL_UP).Row))
    except Exception:
        return 1


def _last_used_column(sheet, row: int = 1) -> int:
    try:
        return max(1, int(sheet.Cells(row, sheet.Columns.Count).End(XL_TO_LEFT).Column))
    except Exception:
        return 1


def _write_rows(sheet, start_row: int, start_col: int, rows: list[list[Any]], chunk_size: int = 4000) -> None:
    if not rows:
        return
    total_columns = len(rows[0])
    for offset in range(0, len(rows), chunk_size):
        chunk = rows[offset : offset + chunk_size]
        top = start_row + offset
        bottom = top + len(chunk) - 1
        sheet.Range(
            sheet.Cells(top, start_col),
            sheet.Cells(bottom, start_col + total_columns - 1),
        ).Value = tuple(tuple(row) for row in chunk)


def _style_title(sheet, title: str, description: str, last_column: int) -> None:
    sheet.Cells(1, 1).Value = title
    sheet.Cells(2, 1).Value = description
    sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Interior.Color = 0x5D3617
    sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Font.Color = 0xFFFFFF
    sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Font.Bold = True
    sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Font.Size = 16
    sheet.Range(sheet.Cells(2, 1), sheet.Cells(2, last_column)).Interior.Color = 0xF7EAD9
    sheet.Range(sheet.Cells(2, 1), sheet.Cells(2, last_column)).WrapText = True
    sheet.Rows(1).RowHeight = 28
    sheet.Rows(2).RowHeight = 34


def _style_header(sheet, row: int, column_count: int, fill_color: int = 0x5D3617) -> None:
    header = sheet.Range(sheet.Cells(row, 1), sheet.Cells(row, column_count))
    header.Interior.Color = fill_color
    header.Font.Color = 0xFFFFFF
    header.Font.Bold = True
    header.HorizontalAlignment = -4108
    header.VerticalAlignment = -4108
    header.WrapText = True
    sheet.Rows(row).RowHeight = 38


def _set_freeze_and_filter(excel, sheet, header_row: int, last_row: int, last_column: int) -> None:
    try:
        sheet.Activate()
        excel.ActiveWindow.FreezePanes = False
        excel.ActiveWindow.SplitColumn = 0
        excel.ActiveWindow.SplitRow = header_row
        excel.ActiveWindow.FreezePanes = True
    except Exception:
        pass

    try:
        if sheet.AutoFilterMode:
            sheet.AutoFilterMode = False
        sheet.Range(
            sheet.Cells(header_row, 1),
            sheet.Cells(last_row, last_column),
        ).AutoFilter()
    except Exception:
        pass


def _backup_workbook(workbook_path: Path, backup_folder: Path) -> Path:
    backup_folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_folder / (
        f"{workbook_path.stem}-before-market-{timestamp}{workbook_path.suffix}"
    )
    shutil.copy2(workbook_path, backup_path)
    return backup_path


def _backup_existing_market_rows(workbook, market_sheet_name: str) -> int:
    try:
        source = workbook.Worksheets(market_sheet_name)
    except Exception:
        return 0

    last_row = _last_used_row(source, 1)
    if last_row < 5:
        return 0

    backup = _get_or_add_sheet(workbook, "Market Data Manual Backup")
    existing_last = _last_used_row(backup, 1)
    if existing_last > 1:
        return 0

    last_col = max(12, _last_used_column(source, 4))
    backup.Range(
        backup.Cells(1, 1),
        backup.Cells(last_row, last_col),
    ).Value = source.Range(
        source.Cells(1, 1),
        source.Cells(last_row, last_col),
    ).Value
    backup.Cells(1, 1).Value = "Market Data Import — Original Rows Backup"
    backup.Cells(2, 1).Value = (
        "Created automatically before the first full database replacement. "
        "This sheet is not read by the scanner."
    )
    return last_row - 4


def write_workbook(
    workbook_path: Path,
    backup_folder: Path,
    cards: list[dict[str, Any]],
    prices: list[PriceVariant],
    variants_by_card: dict[str, list[PriceVariant]],
    changes: list[dict[str, Any]],
    fx: FxRates,
    sync_metadata: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Workbook not found: {workbook_path}. "
            "Place this updater in the scanner folder."
        )

    backup_path = _backup_workbook(workbook_path, backup_folder)

    import win32com.client

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False
    excel.EnableEvents = False

    workbook = excel.Workbooks.Open(str(workbook_path.resolve()))
    manual_rows_backed_up = 0

    try:
        if config.get("backup_existing_market_rows", True):
            manual_rows_backed_up = _backup_existing_market_rows(
                workbook,
                config["market_import_sheet"],
            )

        # -------------------------------------------------------------
        # Market Price Controls + Market Data Import
        # -------------------------------------------------------------
        ensure_controls_sheet(workbook)
        market_controls = read_controls(
            workbook
        )

        market = _get_or_add_sheet(
            workbook,
            config["market_import_sheet"],
        )
        old_last = max(
            5,
            _last_used_row(market, 1),
        )
        market.Range(
            market.Cells(1, 1),
            market.Cells(old_last, 19),
        ).ClearContents()
        market.Range(
            market.Cells(1, 1),
            market.Cells(old_last, 19),
        ).ClearFormats()

        market_headers = [
            "Enabled",
            "Card Name",
            "Set Name",
            "Card Number",
            "Variant",
            "Language",
            "Condition",
            "Market Value (£)",
            "Source",
            "Source Date",
            "Source URL",
            "Notes",
            "Card ID",
            "Base Imported Value (£)",
            "Base Imported Source",
            "Override Value (£)",
            "Override Source",
            "Price Status",
            "Last Synced",
        ]
        _style_title(
            market,
            (
                "Market Data Import — "
                "Authoritative Scanner Values"
            ),
            (
                "Column H is the single market value used by Random, "
                "Snipe, Live, Seller Radar, long-term scoring and AI. "
                "TCGplayer variant-specific market is primary; "
                "Cardmarket trend is fallback only. Verified overrides "
                "from Market Price Controls take priority."
            ),
            len(market_headers),
        )
        market.Range(
            market.Cells(4, 1),
            market.Cells(
                4,
                len(market_headers),
            ),
        ).Value = (
            tuple(market_headers),
        )
        _style_header(
            market,
            4,
            len(market_headers),
        )

        market_rows = []
        override_count = 0
        fallback_count = 0

        for price in prices:
            effective = resolve_effective_value(
                price,
                market_controls,
            )
            if (
                effective.override_value_gbp
                is not None
            ):
                override_count += 1
            if (
                effective.price_status
                == "CARDMARKET FALLBACK"
            ):
                fallback_count += 1

            market_rows.append(
                [
                    "YES",
                    price.card_name,
                    price.set_name,
                    price.card_number,
                    price.variant,
                    "English",
                    "Market reference",
                    effective.effective_value_gbp,
                    effective.effective_source,
                    effective.effective_source_date,
                    effective.effective_source_url,
                    effective.notes,
                    price.card_id,
                    effective.base_value_gbp,
                    effective.base_source,
                    (
                        effective.override_value_gbp
                        if effective.override_value_gbp
                        is not None
                        else ""
                    ),
                    effective.override_source,
                    effective.price_status,
                    sync_metadata["synced_at"],
                ]
            )

        _write_rows(
            market,
            5,
            1,
            market_rows,
        )
        market_last = max(
            5,
            4 + len(market_rows),
        )

        widths = [
            9, 25, 25, 12, 22, 11, 18,
            15, 34, 14, 48, 60, 18, 20,
            34, 18, 25, 23, 20,
        ]
        for index, width in enumerate(
            widths,
            start=1,
        ):
            market.Columns(
                index
            ).ColumnWidth = width

        market.Range(
            f"D5:D{market_last}"
        ).NumberFormat = "@"
        market.Range(
            f"H5:H{market_last}"
        ).NumberFormat = "£0.00"
        market.Range(
            f"N5:N{market_last}"
        ).NumberFormat = "£0.00"
        market.Range(
            f"P5:P{market_last}"
        ).NumberFormat = "£0.00"
        market.Range(
            f"J5:J{market_last}"
        ).NumberFormat = "yyyy-mm-dd"
        market.Range(
            f"S5:S{market_last}"
        ).NumberFormat = (
            "yyyy-mm-dd hh:mm"
        )
        market.Range(
            f"A5:S{market_last}"
        ).VerticalAlignment = -4160
        market.Range(
            f"B5:S{market_last}"
        ).WrapText = True
        _set_freeze_and_filter(
            excel,
            market,
            4,
            market_last,
            len(market_headers),
        )
        mark_controls_applied(
            workbook,
            market_controls,
        )

        # -------------------------------------------------------------
        # Full Card Database
        # -------------------------------------------------------------
        database = _get_or_add_sheet(workbook, config["full_database_sheet"])
        database_headers = [
            "Card ID",
            "Card Name",
            "Set ID",
            "Set Name",
            "Series",
            "Card Number",
            "Printed Total",
            "Rarity",
            "Supertype",
            "Subtypes",
            "Types",
            "HP",
            "Artist",
            "Release Date",
            "Regulation Mark",
            "Evolves From",
            "Evolves To",
            "TCGplayer Updated",
            "Normal Market USD",
            "Holo Market USD",
            "Reverse Market USD",
            "1st Ed Normal USD",
            "1st Ed Holo USD",
            "Cardmarket Updated",
            "Cardmarket Trend EUR",
            "Cardmarket Reverse EUR",
            "Best Market GBP",
            "Best Variant",
            "Best Source",
            "Card Image URL",
            "Source URL",
            "Last Synced",
        ]
        old_last = max(5, _last_used_row(database, 1))
        database.Range(
            database.Cells(1, 1),
            database.Cells(old_last, len(database_headers)),
        ).ClearContents()
        database.Range(
            database.Cells(1, 1),
            database.Cells(old_last, len(database_headers)),
        ).ClearFormats()

        _style_title(
            database,
            "Full English Pokémon Card Database",
            (
                "One row per card from the Pokémon TCG API. Cards without a "
                "current price remain in this database with blank price cells."
            ),
            len(database_headers),
        )
        database.Range(
            database.Cells(4, 1),
            database.Cells(4, len(database_headers)),
        ).Value = (tuple(database_headers),)
        _style_header(database, 4, len(database_headers))

        database_rows = []
        for card in cards:
            card_id = str(card.get("id", ""))
            set_info = card.get("set") or {}
            images = card.get("images") or {}
            tcg = card.get("tcgplayer") or {}
            tcg_prices = tcg.get("prices") or {}
            cm = card.get("cardmarket") or {}
            cm_prices = cm.get("prices") or {}
            card_variants = variants_by_card.get(card_id, [])
            best_price, best_variant, best_source = best_price_summary(card_variants)

            def tcg_market(api_variant: str):
                values = tcg_prices.get(api_variant) or {}
                return values.get("market")

            database_rows.append(
                [
                    card_id,
                    card.get("name", ""),
                    set_info.get("id", ""),
                    set_info.get("name", ""),
                    set_info.get("series", ""),
                    str(card.get("number", "")),
                    set_info.get("printedTotal", ""),
                    card.get("rarity", ""),
                    card.get("supertype", ""),
                    " | ".join(card.get("subtypes") or []),
                    " | ".join(card.get("types") or []),
                    card.get("hp", ""),
                    card.get("artist", ""),
                    set_info.get("releaseDate", ""),
                    card.get("regulationMark", ""),
                    card.get("evolvesFrom", ""),
                    " | ".join(card.get("evolvesTo") or []),
                    tcg.get("updatedAt", ""),
                    tcg_market("normal"),
                    tcg_market("holofoil"),
                    tcg_market("reverseHolofoil"),
                    tcg_market("1stEditionNormal"),
                    tcg_market("1stEditionHolofoil"),
                    cm.get("updatedAt", ""),
                    cm_prices.get("trendPrice"),
                    cm_prices.get("reverseHoloTrend"),
                    best_price,
                    best_variant,
                    best_source,
                    images.get("large", ""),
                    cm.get("url") or tcg.get("url") or "",
                    sync_metadata["synced_at"],
                ]
            )

        _write_rows(database, 5, 1, database_rows)
        db_last = 4 + len(database_rows)
        database.Columns("A").ColumnWidth = 17
        database.Columns("B").ColumnWidth = 24
        database.Columns("C").ColumnWidth = 13
        database.Columns("D").ColumnWidth = 25
        database.Columns("E").ColumnWidth = 22
        database.Columns("F").ColumnWidth = 12
        database.Columns("G").ColumnWidth = 12
        database.Columns("H").ColumnWidth = 20
        database.Columns("I").ColumnWidth = 14
        database.Columns("J").ColumnWidth = 26
        database.Columns("K").ColumnWidth = 18
        database.Columns("L").ColumnWidth = 8
        database.Columns("M").ColumnWidth = 22
        database.Columns("N").ColumnWidth = 13
        database.Columns("O").ColumnWidth = 13
        database.Columns("P").ColumnWidth = 20
        database.Columns("Q").ColumnWidth = 24
        database.Columns("R").ColumnWidth = 15
        database.Columns("S:W").ColumnWidth = 14
        database.Columns("X").ColumnWidth = 17
        database.Columns("Y:AA").ColumnWidth = 17
        database.Columns("AB").ColumnWidth = 22
        database.Columns("AC").ColumnWidth = 29
        database.Columns("AD:AE").ColumnWidth = 48
        database.Columns("AF").ColumnWidth = 20
        database.Range(f"F5:F{db_last}").NumberFormat = "@"
        database.Range(f"N5:N{db_last}").NumberFormat = "yyyy-mm-dd"
        database.Range(f"S5:W{db_last}").NumberFormat = '$0.00'
        database.Range(f"Y5:Z{db_last}").NumberFormat = '€0.00'
        database.Range(f"AA5:AA{db_last}").NumberFormat = '£0.00'
        database.Range(f"A5:AF{db_last}").VerticalAlignment = -4160
        _set_freeze_and_filter(excel, database, 4, db_last, len(database_headers))

        # -------------------------------------------------------------
        # Price Changes
        # -------------------------------------------------------------
        changes_sheet = _get_or_add_sheet(
            workbook,
            config["price_changes_sheet"],
        )
        change_headers = [
            "Observed At",
            "Card ID",
            "Card Name",
            "Set Name",
            "Card Number",
            "Variant",
            "Previous Price (£)",
            "Current Price (£)",
            "Change (£)",
            "Change (%)",
            "Direction",
            "Source",
            "Source Date",
            "Source URL",
        ]
        old_last = max(5, _last_used_row(changes_sheet, 1))
        changes_sheet.Range(
            changes_sheet.Cells(1, 1),
            changes_sheet.Cells(old_last, len(change_headers)),
        ).ClearContents()
        changes_sheet.Range(
            changes_sheet.Cells(1, 1),
            changes_sheet.Cells(old_last, len(change_headers)),
        ).ClearFormats()

        _style_title(
            changes_sheet,
            "Daily Pokémon Market Price Changes",
            (
                "Compares the latest prices with the previous successful run. "
                "The first run creates a baseline and therefore has no changes."
            ),
            len(change_headers),
        )
        changes_sheet.Range(
            changes_sheet.Cells(4, 1),
            changes_sheet.Cells(4, len(change_headers)),
        ).Value = (tuple(change_headers),)
        _style_header(changes_sheet, 4, len(change_headers), fill_color=0x006100)

        max_changes = int(config["maximum_change_rows_in_excel"])
        display_changes = sorted(
            changes,
            key=lambda item: abs(item["change_percent"]),
            reverse=True,
        )[:max_changes]
        change_rows = [
            [
                change["observed_at"],
                change["card_id"],
                change["card_name"],
                change["set_name"],
                change["card_number"],
                change["variant"],
                change["previous_price_gbp"],
                change["current_price_gbp"],
                change["change_gbp"],
                change["change_percent"],
                "UP" if change["change_gbp"] > 0 else "DOWN",
                change["source"],
                change["source_date"],
                change["source_url"],
            ]
            for change in display_changes
        ]
        _write_rows(changes_sheet, 5, 1, change_rows)
        changes_last = max(5, 4 + len(change_rows))
        changes_sheet.Columns("A").ColumnWidth = 20
        changes_sheet.Columns("B").ColumnWidth = 17
        changes_sheet.Columns("C").ColumnWidth = 24
        changes_sheet.Columns("D").ColumnWidth = 25
        changes_sheet.Columns("E").ColumnWidth = 12
        changes_sheet.Columns("F").ColumnWidth = 23
        changes_sheet.Columns("G:I").ColumnWidth = 16
        changes_sheet.Columns("J").ColumnWidth = 13
        changes_sheet.Columns("K").ColumnWidth = 11
        changes_sheet.Columns("L").ColumnWidth = 29
        changes_sheet.Columns("M").ColumnWidth = 13
        changes_sheet.Columns("N").ColumnWidth = 48
        changes_sheet.Range(f"E5:E{changes_last}").NumberFormat = "@"
        changes_sheet.Range(f"G5:I{changes_last}").NumberFormat = '£0.00'
        changes_sheet.Range(f"J5:J{changes_last}").NumberFormat = '0.0%'
        _set_freeze_and_filter(
            excel,
            changes_sheet,
            4,
            changes_last,
            len(change_headers),
        )

        # -------------------------------------------------------------
        # Summary
        # -------------------------------------------------------------
        summary = _get_or_add_sheet(workbook, config["summary_sheet"])
        summary.Range("A1:F40").ClearContents()
        summary.Range("A1:F40").ClearFormats()
        _style_title(
            summary,
            "Pokémon Market Database — Update Summary",
            (
                "Daily status for the full English card catalogue and GBP "
                "reference-price import."
            ),
            6,
        )

        cardmarket_count = sum(
            1
            for price in prices
            if "Cardmarket" in price.source
        )
        tcg_count = sum(
            1
            for price in prices
            if "TCGplayer" in price.source
        )
        kpis = [
            ["Metric", "Value", "Meaning"],
            ["Last successful refresh", sync_metadata["synced_at"], "Local completion time"],
            ["English cards downloaded", len(cards), "One record per API card ID"],
            ["Priced variants imported", len(prices), "Rows written to Market Data Import"],
            [
                "TCGplayer primary variants",
                tcg_count,
                "Variant-specific market values",
            ],
            [
                "Cardmarket fallback variants",
                cardmarket_count,
                "Used only when exact TCGplayer variant is unavailable",
            ],
            [
                "Verified overrides applied",
                override_count,
                "Market Price Controls values replacing the base import",
            ],
            [
                "Price changes detected",
                len(changes),
                "Compared with previous successful run",
            ],
            ["EUR → GBP rate", fx.eur_to_gbp, fx.source],
            ["USD → GBP rate", fx.usd_to_gbp, fx.source],
            ["FX rate date", fx.rate_date, "Reference-rate date"],
            ["API key used", "YES" if sync_metadata["api_key_used"] else "NO", "Free key is recommended for faster updates"],
            ["API pages downloaded", sync_metadata["pages"], "Pagination requests"],
            ["Original market rows backed up", manual_rows_backed_up, "Stored in Market Data Manual Backup"],
            ["Workbook backup", str(backup_path), "Created before Excel changes"],
        ]
        summary.Range("A4:C19").Value = tuple(tuple(row) for row in kpis)
        _style_header(summary, 4, 3)
        summary.Range("A5:A19").Font.Bold = True
        summary.Range("A5:A19").Interior.Color = 0xD9EAF7
        summary.Range("B5:B19").Interior.Color = 0xE2F0D9
        summary.Columns("A").ColumnWidth = 31
        summary.Columns("B").ColumnWidth = 58
        summary.Columns("C").ColumnWidth = 52
        summary.Range("B11:B12").NumberFormat = "0.000000"
        summary.Range("A4:C19").WrapText = True
        summary.Rows("5:19").RowHeight = 24

        # -------------------------------------------------------------
        # Price Import Log append
        # -------------------------------------------------------------
        log = _get_or_add_sheet(workbook, config["price_log_sheet"])
        if _last_used_row(log, 1) < 3:
            log.Cells(1, 1).Value = "Market Price Import Log"
            log.Range("A3:H3").Value = (
                (
                    "Timestamp",
                    "Input File",
                    "Rows Read",
                    "Rows Imported",
                    "Rows Rejected",
                    "Duplicates Replaced",
                    "Source",
                    "Message",
                ),
            )
            _style_header(log, 3, 8)

        log_row = _last_used_row(log, 1) + 1
        log.Range(
            log.Cells(log_row, 1),
            log.Cells(log_row, 8),
        ).Value = (
            (
                sync_metadata["synced_at"],
                "Pokémon TCG API v2",
                len(cards),
                len(prices),
                len(cards) - len(variants_by_card),
                0,
                "TCGplayer primary + Cardmarket fallback + verified overrides",
                (
                    f"Full daily sync; {len(changes)} price changes; "
                    f"EUR/GBP {fx.eur_to_gbp:.6f}; "
                    f"USD/GBP {fx.usd_to_gbp:.6f}"
                ),
            ),
        )

        workbook.Save()
        return {
            "backup_path": str(backup_path),
            "manual_rows_backed_up": manual_rows_backed_up,
            "market_rows_written": len(prices),
            "database_rows_written": len(cards),
            "changes_written": len(display_changes),
        }
    finally:
        workbook.Close(SaveChanges=True)
        excel.EnableEvents = True
        excel.ScreenUpdating = True
        excel.Quit()
