from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from market_links import market_links_for_fields


XL_UP = -4162
XL_TO_LEFT = -4159
XL_SHIFT_TO_RIGHT = -4161

MARKET_HEADERS = [
    "UK Market",
    "TCGplayer",
    "Cardmarket",
    "PriceCharting",
]
MARKET_LABELS = [
    "Open UK Market",
    "Open TCGplayer",
    "Open Cardmarket",
    "Open PriceCharting",
]


def header_map(sheet, row: int) -> dict[str, int]:
    last = int(
        sheet.Cells(row, sheet.Columns.Count).End(XL_TO_LEFT).Column
    )
    output: dict[str, int] = {}
    for column in range(1, last + 1):
        value = str(sheet.Cells(row, column).Value or "").strip()
        if value:
            output[value] = column
    return output


def last_data_row(sheet, column: int, minimum: int) -> int:
    return max(
        minimum,
        int(sheet.Cells(sheet.Rows.Count, column).End(XL_UP).Row),
    )


def split_card_label(value: Any) -> tuple[str, str, str, str]:
    parts = [part.strip() for part in str(value or "").split("|")]
    parts += [""] * (4 - len(parts))
    return tuple(parts[:4])


def card_fields(sheet, row: int, headers: dict[str, int]) -> tuple[str, str, str, str]:
    if "Card Name" in headers:
        return (
            str(sheet.Cells(row, headers["Card Name"]).Value or ""),
            str(sheet.Cells(row, headers.get("Set", 0)).Value or ""),
            str(sheet.Cells(row, headers.get("Card Number", 0)).Value or ""),
            str(sheet.Cells(row, headers.get("Variant", 0)).Value or ""),
        )
    label_header = "Selected Card" if "Selected Card" in headers else "Card Match"
    if label_header in headers:
        return split_card_label(
            sheet.Cells(row, headers[label_header]).Value
        )
    search_header = (
        "Matched Card Search"
        if "Matched Card Search" in headers
        else "Search Query"
    )
    query = str(sheet.Cells(row, headers.get(search_header, 1)).Value or "")
    query = re.sub(r"^Random Range:\s*", "", query, flags=re.I)
    return query, "", "", ""


def insert_market_columns(
    sheet,
    header_row: int,
    data_start: int,
    sold_header: str = "Sold Comparables",
) -> int:
    headers = header_map(sheet, header_row)
    sold_column = headers.get(sold_header)
    if not sold_column:
        return 0

    first_new = sold_column + 1
    if str(sheet.Cells(header_row, first_new).Value or "") != "UK Market":
        sheet.Range(
            sheet.Columns(first_new),
            sheet.Columns(first_new + 3),
        ).Insert(Shift=XL_SHIFT_TO_RIGHT)

    for offset, header in enumerate(MARKET_HEADERS):
        cell = sheet.Cells(header_row, first_new + offset)
        cell.Value = header
        cell.ColumnWidth = 16 if header != "PriceCharting" else 17

    headers = header_map(sheet, header_row)
    last_row = last_data_row(sheet, 1, data_start - 1)
    if last_row < data_start:
        return first_new

    for row in range(data_start, last_row + 1):
        name, set_name, number, variant = card_fields(sheet, row, headers)
        if not str(name).strip():
            continue
        links = market_links_for_fields(name, set_name, number, variant)
        addresses = [
            links.uk_market,
            links.tcgplayer,
            links.cardmarket,
            links.pricecharting,
        ]
        for offset, (address, label) in enumerate(
            zip(addresses, MARKET_LABELS)
        ):
            cell = sheet.Cells(row, first_new + offset)
            try:
                cell.Hyperlinks.Delete()
            except Exception:
                pass
            sheet.Hyperlinks.Add(
                Anchor=cell,
                Address=address,
                TextToDisplay=label,
            )
    return first_new


def extend_snipe_queue(sheet) -> None:
    headers = header_map(sheet, 4)
    if "Sold Comparables" not in headers:
        start = headers.get("Card Image", 25) + 1
        new_headers = ["Sold Comparables", *MARKET_HEADERS]
        for offset, header in enumerate(new_headers):
            sheet.Cells(4, start + offset).Value = header
            sheet.Columns(start + offset).ColumnWidth = (
                20 if offset == 0 else 16
            )
    else:
        insert_market_columns(sheet, 4, 5)
        return

    headers = header_map(sheet, 4)
    last_row = last_data_row(sheet, 1, 4)
    for row in range(5, last_row + 1):
        query = str(
            sheet.Cells(row, headers.get("Search Query", 23)).Value or ""
        )
        query = re.sub(r"^Random Range:\s*", "", query, flags=re.I)
        card_label = str(
            sheet.Cells(row, headers.get("Selected Card", 4)).Value or ""
        )
        name, set_name, number, variant = split_card_label(card_label)
        if not name:
            name = query
        links = market_links_for_fields(name, set_name, number, variant)
        sold = (
            "https://www.ebay.co.uk/sch/i.html?_nkw="
            + __import__("urllib.parse").parse.quote_plus(query)
            + "&_sacat=0&LH_Sold=1&LH_Complete=1&LH_PrefLoc=1&_sop=13"
        )
        for column, address, label in (
            (headers["Sold Comparables"], sold, "Open Sold Results"),
            (headers["UK Market"], links.uk_market, "Open UK Market"),
            (headers["TCGplayer"], links.tcgplayer, "Open TCGplayer"),
            (headers["Cardmarket"], links.cardmarket, "Open Cardmarket"),
            (headers["PriceCharting"], links.pricecharting, "Open PriceCharting"),
        ):
            try:
                sheet.Cells(row, column).Hyperlinks.Delete()
            except Exception:
                pass
            sheet.Hyperlinks.Add(
                Anchor=sheet.Cells(row, column),
                Address=address,
                TextToDisplay=label,
            )


def widen_title(sheet, row: int = 1) -> None:
    headers_row = 8 if str(sheet.Cells(8, 1).Value or "") == "Rank" else 4
    if sheet.Name == "Random Range Sniper":
        headers_row = 23
    if sheet.Name == "Opportunity Archive":
        headers_row = 3
    last_col = int(
        sheet.Cells(headers_row, sheet.Columns.Count).End(XL_TO_LEFT).Column
    )
    try:
        value = sheet.Cells(row, 1).Value
        sheet.Rows(row).UnMerge()
        sheet.Range(
            sheet.Cells(row, 1),
            sheet.Cells(row, last_col),
        ).Merge()
        sheet.Cells(row, 1).Value = value
    except Exception:
        pass


def main() -> int:
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env", override=True, encoding="utf-8-sig")
    workbook_path = Path(
        os.getenv(
            "WORKBOOK_PATH",
            "Pokemon-Auction-Scanner-Dashboard.xlsx",
        )
    )
    if not workbook_path.is_absolute():
        workbook_path = root / workbook_path
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    backup_folder = root / "backups"
    backup_folder.mkdir(exist_ok=True)
    backup_path = backup_folder / (
        f"{workbook_path.stem}-before-phase5-4-1-smart-market-links-"
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

    updated: list[str] = []
    try:
        targets = [
            ("Random Range Sniper", 23, 24),
            ("Random Snipe Results", 4, 5),
            ("Random Snipe Queue", 4, 5),
            ("Random Snipe History", 4, 5),
            ("Live Opportunities", 4, 5),
            ("Opportunity Archive", 3, 4),
        ]
        for name, header_row, data_start in targets:
            try:
                sheet = workbook.Worksheets(name)
            except Exception:
                continue
            if insert_market_columns(sheet, header_row, data_start):
                updated.append(name)
                widen_title(sheet)

        try:
            queue = workbook.Worksheets("Snipe Queue")
            extend_snipe_queue(queue)
            updated.append("Snipe Queue")
        except Exception:
            pass

        for index in range(1, workbook.Worksheets.Count + 1):
            sheet = workbook.Worksheets(index)
            if str(sheet.Name).startswith("Seller -"):
                if insert_market_columns(sheet, 8, 9):
                    updated.append(str(sheet.Name))
                    widen_title(sheet)

        workbook.Save()
    finally:
        workbook.Close(SaveChanges=True)
        excel.EnableEvents = True
        excel.ScreenUpdating = True
        excel.Quit()

    print("PHASE 5.4.1 SMART MARKET-LINK REFRESH SUCCESSFUL")
    print(f"Workbook backup: {backup_path}")
    print("Updated worksheets:")
    for name in updated:
        print(f"  - {name}")
    print()
    print("Refreshed after Sold Comparables:")
    print("  UK Market | TCGplayer | Cardmarket | PriceCharting")
    print("Query format: clean card name + collector number/ID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
