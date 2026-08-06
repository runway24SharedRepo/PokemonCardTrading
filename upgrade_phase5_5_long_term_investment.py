from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dotenv import load_dotenv

from long_term_excel import LongTermWorkbookManager
from long_term_investment import (
    LONG_TERM_HEADERS,
    apply_assessment,
    assessment_values,
    assess_candidate,
    normalize_text,
)


XL_UP = -4162
XL_TO_LEFT = -4159
XL_SHIFT_TO_RIGHT = -4161
XL_CENTER = -4108


LONG_TERM_WIDTHS = [
    15, 24, 26, 18, 18, 19, 20, 21, 18, 20, 15, 25, 18, 55, 55,
]


def header_map(sheet, row: int) -> dict[str, int]:
    last = int(sheet.Cells(row, sheet.Columns.Count).End(XL_TO_LEFT).Column)
    output: dict[str, int] = {}
    for column in range(1, last + 1):
        value = str(sheet.Cells(row, column).Value or "").strip()
        if value:
            output[value] = column
    return output


def last_data_row(sheet, column: int, minimum: int) -> int:
    return max(minimum, int(sheet.Cells(sheet.Rows.Count, column).End(XL_UP).Row))


def split_card_label(value: Any) -> tuple[str, str, str, str]:
    parts = [part.strip() for part in str(value or "").split("|")]
    parts += [""] * (4 - len(parts))
    return tuple(parts[:4])


def value_for(sheet, row: int, headers: dict[str, int], *names: str) -> Any:
    for name in names:
        column = headers.get(name)
        if column:
            return sheet.Cells(row, column).Value
    return None


def card_fields(sheet, row: int, headers: dict[str, int]) -> tuple[str, str, str, str, str]:
    card_id = str(value_for(sheet, row, headers, "Card ID") or "").strip()
    if "Card Name" in headers:
        return (
            card_id,
            str(value_for(sheet, row, headers, "Card Name") or ""),
            str(value_for(sheet, row, headers, "Set") or ""),
            str(value_for(sheet, row, headers, "Card Number") or ""),
            str(value_for(sheet, row, headers, "Variant") or ""),
        )
    for label in ("Selected Card", "Card Match"):
        if label in headers:
            name, set_name, number, variant = split_card_label(
                value_for(sheet, row, headers, label)
            )
            return card_id, name, set_name, number, variant
    query = str(
        value_for(
            sheet,
            row,
            headers,
            "Matched Card Search",
            "Search Query",
        )
        or ""
    )
    query = re.sub(r"^Random Range:\s*", "", query, flags=re.I)
    return card_id, query, "", "", ""


def minimum_ratio(sheet, row: int, headers: dict[str, int]) -> float | None:
    values: list[float] = []
    for name in (
        "Bid / Market",
        "Buy Now / Market",
        "Cost / Market",
        "Delivered / Market",
        "Best Ratio",
        "Best / Market",
    ):
        value = value_for(sheet, row, headers, name)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            values.append(number if number <= 3 else number / 100)
    discount = value_for(sheet, row, headers, "Best Discount")
    try:
        number = float(discount)
        if 0 <= number <= 1:
            values.append(1 - number)
    except (TypeError, ValueError):
        pass
    return min(values) if values else None


def database_index(workbook) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_fields: dict[tuple[str, str, str], dict[str, Any]] = {}
    try:
        sheet = workbook.Worksheets("Full Card Database")
    except Exception:
        return by_id, by_fields
    last = last_data_row(sheet, 1, 4)
    values = sheet.Range(f"A5:AF{last}").Value
    if values is None:
        return by_id, by_fields
    rows = list(values) if isinstance(values, tuple) and values and isinstance(values[0], tuple) else [values]
    for row in rows:
        card_id = str(row[0] or "").strip()
        name = str(row[1] or "").strip()
        set_name = str(row[3] or "").strip()
        number = str(row[5] or "").strip()
        details = {
            "card_id": card_id,
            "name": name,
            "set_name": set_name,
            "number": number,
            "rarity": str(row[7] or "").strip(),
            "supertype": str(row[8] or "").strip(),
            "release_date": row[13],
            "image_url": str(row[29] or "").strip(),
        }
        if card_id:
            by_id[card_id.casefold()] = details
        by_fields[(name.casefold(), set_name.casefold(), number.casefold())] = details
    return by_id, by_fields


def market_index(workbook) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    output: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    try:
        sheet = workbook.Worksheets("Market Data Import")
    except Exception:
        return output
    last = last_data_row(sheet, 1, 4)
    values = sheet.Range(f"A5:L{last}").Value
    if values is None:
        return output
    rows = list(values) if isinstance(values, tuple) and values and isinstance(values[0], tuple) else [values]
    for row in rows:
        name = str(row[1] or "").strip()
        set_name = str(row[2] or "").strip()
        number = str(row[3] or "").strip()
        variant = str(row[4] or "").strip()
        try:
            market = float(row[7] or 0)
        except (TypeError, ValueError):
            market = 0.0
        output[(name.casefold(), set_name.casefold(), number.casefold(), variant.casefold())] = {
            "market_value": market,
            "source": str(row[8] or ""),
            "source_date": row[9],
            "source_url": str(row[10] or ""),
        }
    return output


def insert_long_term_columns(sheet, header_row: int, data_start: int) -> int:
    headers = header_map(sheet, header_row)
    price_column = headers.get("PriceCharting")
    if not price_column:
        return 0
    first = price_column + 1
    if str(sheet.Cells(header_row, first).Value or "") != LONG_TERM_HEADERS[0]:
        sheet.Range(
            sheet.Columns(first),
            sheet.Columns(first + len(LONG_TERM_HEADERS) - 1),
        ).Insert(Shift=XL_SHIFT_TO_RIGHT)
    for offset, (header, width) in enumerate(zip(LONG_TERM_HEADERS, LONG_TERM_WIDTHS)):
        cell = sheet.Cells(header_row, first + offset)
        cell.Value = header
        cell.ColumnWidth = width
        cell.WrapText = True
        cell.HorizontalAlignment = XL_CENTER
    header_range = sheet.Range(
        sheet.Cells(header_row, first),
        sheet.Cells(header_row, first + len(LONG_TERM_HEADERS) - 1),
    )
    header_range.Interior.Color = 12164479  # dark blue in Excel BGR form
    header_range.Font.Color = 16777215
    header_range.Font.Bold = True
    return first


def style_assessment(sheet, row: int, first: int, score: int) -> None:
    if score >= 90:
        fill, font = 3506772, 16777215
    elif score >= 80:
        fill, font = 13561798, 24832
    elif score >= 70:
        fill, font = 14348258, 2315831
    elif score >= 60:
        fill, font = 10284031, 26268
    else:
        fill, font = 13551615, 393372
    for column in (first, first + 1):
        sheet.Cells(row, column).Interior.Color = fill
        sheet.Cells(row, column).Font.Color = font
        sheet.Cells(row, column).Font.Bold = True
        sheet.Cells(row, column).HorizontalAlignment = XL_CENTER


def widen_title(sheet, header_row: int) -> None:
    last = int(sheet.Cells(header_row, sheet.Columns.Count).End(XL_TO_LEFT).Column)
    for row in (1, 2):
        try:
            value = sheet.Cells(row, 1).Value
            sheet.Rows(row).UnMerge()
            sheet.Range(sheet.Cells(row, 1), sheet.Cells(row, last)).Merge()
            sheet.Cells(row, 1).Value = value
        except Exception:
            pass


def refresh_sheet_rows(
    sheet,
    header_row: int,
    data_start: int,
    first: int,
    manager: LongTermWorkbookManager,
    db_by_id: dict[str, dict[str, Any]],
    db_by_fields: dict[tuple[str, str, str], dict[str, Any]],
    markets: dict[tuple[str, str, str, str], dict[str, Any]],
) -> int:
    headers = header_map(sheet, header_row)
    last = last_data_row(sheet, 1, data_start - 1)
    if last < data_start:
        return 0
    context = manager.context(refresh=True)
    updated = 0
    for row in range(data_start, last + 1):
        card_id, name, set_name, number, variant = card_fields(sheet, row, headers)
        if not name and not card_id:
            continue
        details = db_by_id.get(card_id.casefold()) if card_id else None
        if details is None:
            details = db_by_fields.get((name.casefold(), set_name.casefold(), number.casefold()), {})
        market = markets.get((name.casefold(), set_name.casefold(), number.casefold(), variant.casefold()), {})
        market_value = value_for(sheet, row, headers, "Market (£)", "Market Value (£)", "Current Market / Copy (£)")
        try:
            market_value = float(market_value or market.get("market_value", 0) or 0)
        except (TypeError, ValueError):
            market_value = 0.0
        candidate = SimpleNamespace(
            card_id=card_id or details.get("card_id", ""),
            name=name or details.get("name", ""),
            set_name=set_name or details.get("set_name", ""),
            number=number or details.get("number", ""),
            variant=variant,
            rarity=details.get("rarity", ""),
            supertype=details.get("supertype", ""),
            release_date=details.get("release_date"),
            market_value=market_value,
            source=market.get("source", ""),
            source_date=market.get("source_date"),
            source_url=market.get("source_url", ""),
            price_change=0.0,
        )
        condition_flag = str(value_for(sheet, row, headers, "Condition Flag") or "UNKNOWN")
        condition_details = " ".join(
            str(value_for(sheet, row, headers, field) or "")
            for field in ("Condition", "Condition Details")
        ).strip()
        assessment = assess_candidate(
            candidate,
            context,
            ratio=minimum_ratio(sheet, row, headers),
            condition_flag=condition_flag,
            condition_details=condition_details,
        )
        apply_assessment(candidate, assessment)
        values = assessment_values(candidate)
        sheet.Range(
            sheet.Cells(row, first),
            sheet.Cells(row, first + len(values) - 1),
        ).Value = (tuple(values),)
        style_assessment(sheet, row, first, assessment.long_term_score)
        updated += 1
    return updated


def main() -> int:
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env", override=True, encoding="utf-8-sig")
    workbook_path = Path(os.getenv("WORKBOOK_PATH", "Pokemon-Auction-Scanner-Dashboard.xlsx"))
    if not workbook_path.is_absolute():
        workbook_path = root / workbook_path
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    backup_folder = root / "backups"
    backup_folder.mkdir(exist_ok=True)
    backup_path = backup_folder / (
        f"{workbook_path.stem}-before-phase5-5-long-term-"
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        f"{workbook_path.suffix}"
    )
    shutil.copy2(workbook_path, backup_path)

    import win32com.client

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False
    excel.EnableEvents = False
    workbook = excel.Workbooks.Open(str(workbook_path.resolve()))

    updated: list[tuple[str, int]] = []
    try:
        manager = LongTermWorkbookManager(workbook)
        manager.ensure_sheets()
        db_by_id, db_by_fields = database_index(workbook)
        markets = market_index(workbook)

        targets = [
            ("Random Range Sniper", 23, 24),
            ("Random Snipe Results", 4, 5),
            ("Random Snipe Queue", 4, 5),
            ("Random Snipe History", 4, 5),
            ("Snipe Queue", 4, 5),
            ("Live Opportunities", 4, 5),
            ("Opportunity Archive", 3, 4),
        ]
        for name, header_row, data_start in targets:
            try:
                sheet = workbook.Worksheets(name)
            except Exception:
                continue
            first = insert_long_term_columns(sheet, header_row, data_start)
            if not first:
                continue
            count = refresh_sheet_rows(
                sheet,
                header_row,
                data_start,
                first,
                manager,
                db_by_id,
                db_by_fields,
                markets,
            )
            widen_title(sheet, header_row)
            updated.append((name, count))

        for index in range(1, workbook.Worksheets.Count + 1):
            sheet = workbook.Worksheets(index)
            if not str(sheet.Name).startswith("Seller -"):
                continue
            first = insert_long_term_columns(sheet, 8, 9)
            if not first:
                continue
            count = refresh_sheet_rows(
                sheet,
                8,
                9,
                first,
                manager,
                db_by_id,
                db_by_fields,
                markets,
            )
            widen_title(sheet, 8)
            updated.append((str(sheet.Name), count))

        manager.refresh_portfolio(
            SimpleNamespace(
                card_id=details.get("card_id", ""),
                name=details.get("name", ""),
                set_name=details.get("set_name", ""),
                number=details.get("number", ""),
                variant=variant,
                rarity=details.get("rarity", ""),
                supertype=details.get("supertype", ""),
                release_date=details.get("release_date"),
                market_value=market.get("market_value", 0),
                source=market.get("source", ""),
                source_date=market.get("source_date"),
                source_url=market.get("source_url", ""),
                price_change=0.0,
            )
            for (name_key, set_key, number_key, variant), market in markets.items()
            for details in [db_by_fields.get((name_key, set_key, number_key), {
                "card_id": "", "name": name_key, "set_name": set_key, "number": number_key,
                "rarity": "", "supertype": "", "release_date": None,
            })]
        )
        manager.refresh_dashboard()
        workbook.Save()
    finally:
        workbook.Close(SaveChanges=True)
        excel.EnableEvents = True
        excel.ScreenUpdating = True
        excel.Quit()

    print("PHASE 5.5 LONG-TERM INVESTMENT ENGINE INSTALLED")
    print(f"Workbook backup: {backup_path}")
    print("New worksheets:")
    print("  Investment Settings")
    print("  Long-Term Targets")
    print("  Portfolio Vault")
    print("  Price History")
    print("  Long-Term Dashboard")
    print("Updated opportunity modes:")
    for name, count in updated:
        print(f"  {name}: {count} existing row(s) assessed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
