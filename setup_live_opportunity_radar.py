from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


XL_CENTER = -4108
XL_TOP = -4160


def get_or_add_sheet(workbook, name: str):
    try:
        return workbook.Worksheets(name), False
    except Exception:
        sheet = workbook.Worksheets.Add(
            After=workbook.Worksheets(
                workbook.Worksheets.Count
            )
        )
        sheet.Name = name
        return sheet, True


def set_validation(cell_range, values: list[str]) -> None:
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


def style_title(
    sheet,
    last_column: int,
    title: str,
    description: str,
    fill: int,
) -> None:
    sheet.Cells(1, 1).Value = title
    sheet.Cells(2, 1).Value = description

    title_range = sheet.Range(
        sheet.Cells(1, 1),
        sheet.Cells(1, last_column),
    )
    title_range.Interior.Color = fill
    title_range.Font.Color = 0xFFFFFF
    title_range.Font.Bold = True
    title_range.Font.Size = 17

    description_range = sheet.Range(
        sheet.Cells(2, 1),
        sheet.Cells(2, last_column),
    )
    description_range.Interior.Color = 0xF7EAD9
    description_range.WrapText = True

    sheet.Rows(1).RowHeight = 30
    sheet.Rows(2).RowHeight = 44


def style_header(
    sheet,
    row: int,
    columns: int,
    fill: int,
) -> None:
    header = sheet.Range(
        sheet.Cells(row, 1),
        sheet.Cells(row, columns),
    )
    header.Interior.Color = fill
    header.Font.Color = 0xFFFFFF
    header.Font.Bold = True
    header.HorizontalAlignment = XL_CENTER
    header.VerticalAlignment = XL_CENTER
    header.WrapText = True
    sheet.Rows(row).RowHeight = 45


def add_borders(sheet, address: str) -> None:
    rng = sheet.Range(address)
    for edge in range(7, 13):
        try:
            rng.Borders(edge).LineStyle = 1
            rng.Borders(edge).Color = 0xD9D9D9
            rng.Borders(edge).Weight = 2
        except Exception:
            pass


def setup_scanner_settings(workbook) -> None:
    sheet, _ = get_or_add_sheet(
        workbook,
        "Scanner Settings",
    )

    sheet.Cells(12, 1).Value = "Radar results per request"
    sheet.Cells(12, 2).Value = 200
    sheet.Cells(12, 3).Value = (
        "Broad auction listings returned per API page; maximum 200"
    )

    sheet.Cells(13, 1).Value = "Maximum broad search requests"
    sheet.Cells(13, 2).Value = 5
    sheet.Cells(13, 3).Value = (
        "Editable cap for paginated broad radar searches"
    )

    sheet.Cells(14, 1).Value = "Ending within hours"
    sheet.Cells(14, 2).Value = 24
    sheet.Cells(14, 3).Value = (
        "Maximum auction time remaining"
    )

    additions = [
        (
            "Minimum minutes remaining",
            2,
            "Ignore auctions too close to ending to inspect safely",
        ),
        (
            "Maximum total API calls",
            100,
            "Hard cap including searches and condition detail calls",
        ),
        (
            "Maximum live rows",
            250,
            "Workbook output cap",
        ),
        (
            "Broad radar query",
            "pokemon card",
            "Basic non-card-specific eBay search",
        ),
        (
            "Expand GREEN sellers",
            "YES",
            "Check other auctions belonging to GREEN sellers",
        ),
        (
            "Maximum GREEN sellers",
            5,
            "Maximum sellers expanded per run",
        ),
        (
            "Seller listings to inspect",
            100,
            "Maximum auctions requested from each GREEN seller",
        ),
        (
            "Opportunities per seller",
            5,
            "Additional GREEN/AMBER rows shown below each seller",
        ),
        (
            "Detailed condition checks",
            50,
            "Maximum getItem condition lookups per run",
        ),
        (
            "Archive previous live results",
            "YES",
            "Move the previous live table into Opportunity Archive",
        ),
    ]

    start_row = 19
    for offset, (label, value, purpose) in enumerate(additions):
        row = start_row + offset
        sheet.Cells(row, 1).Value = label
        sheet.Cells(row, 2).Value = value
        sheet.Cells(row, 3).Value = purpose

    sheet.Range("A19:A28").Interior.Color = 0xE7D3B8
    sheet.Range("A19:A28").Font.Bold = True
    sheet.Range("B19:B28").Interior.Color = 0xCCF2FF
    sheet.Range("B19:B28").Font.Color = 0x0000FF
    sheet.Range("C19:C28").WrapText = True

    set_validation(sheet.Range("B23"), ["YES", "NO"])
    set_validation(sheet.Range("B28"), ["YES", "NO"])
    set_validation(
        sheet.Range("B19"),
        ["1", "2", "3", "5", "10"],
    )
    set_validation(
        sheet.Range("B20"),
        ["25", "50", "75", "100", "150", "200"],
    )
    set_validation(
        sheet.Range("B24"),
        ["1", "2", "3", "5", "10"],
    )
    set_validation(
        sheet.Range("B25"),
        ["25", "50", "100", "150", "200"],
    )
    set_validation(
        sheet.Range("B26"),
        ["1", "3", "5", "10", "15"],
    )
    set_validation(
        sheet.Range("B27"),
        ["10", "25", "50", "75", "100"],
    )

    sheet.Columns("A").ColumnWidth = 34
    sheet.Columns("B").ColumnWidth = 22
    sheet.Columns("C").ColumnWidth = 66


def setup_live_sheet(workbook) -> None:
    sheet, _ = get_or_add_sheet(
        workbook,
        "Live Opportunities",
    )
    sheet.Range("A1:AR1004").ClearContents()
    sheet.Range("A1:AR1004").ClearFormats()

    style_title(
        sheet,
        44,
        "Live Opportunity Radar — UK Pokémon Auctions Ending Soon",
        (
            "Broad eBay auction radar. Listing, sold-comparable, UK and "
            "global market-tracker links are grouped beside Cost / Market."
        ),
        0x17365D,
    )

    headers = [
        "Rank", "Decision", "Recommended Action", "Score",
        "Discovery Source", "Parent Item ID", "Card Match", "Card ID",
        "Set", "Card Number", "Variant", "Rarity", "Listing Title",
        "Item ID", "Current Bid (£)", "Postage (£)", "Delivered (£)",
        "Market (£)", "Cost / Market", "Direct Listing", "Card Image",
        "Auction Search", "Sold Comparables", "UK Market", "TCGplayer",
        "Cardmarket", "PriceCharting", "Target Delivered (£)",
        "Maximum Bid (£)", "Bid Headroom (£)", "Ends At",
        "Minutes Remaining", "Bid Count", "Seller", "Feedback %",
        "Feedback Count", "Condition", "Condition Flag",
        "Condition Details", "Match Confidence", "Matched Card Search",
        "Status", "Notes", "Last Refreshed",
    ]

    sheet.Range("A4:AR4").Value = (tuple(headers),)
    style_header(sheet, 4, len(headers), 0x17365D)
    add_borders(sheet, "A4:AR1004")

    widths = {
        "A": 7, "B": 11, "C": 20, "D": 9, "E": 18, "F": 20,
        "G": 40, "H": 17, "I": 24, "J": 12, "K": 21, "L": 18,
        "M": 52, "N": 20, "O": 13, "P": 11, "Q": 13, "R": 12,
        "S": 13, "T": 17, "U": 17, "V": 19, "W": 20,
        "X": 16, "Y": 16, "Z": 16, "AA": 17,
        "AB": 17, "AC": 15, "AD": 15, "AE": 18,
        "AF": 16, "AG": 10, "AH": 18, "AI": 12, "AJ": 14,
        "AK": 30, "AL": 14, "AM": 50, "AN": 16, "AO": 37,
        "AP": 12, "AQ": 55, "AR": 19,
    }
    for column, width in widths.items():
        sheet.Columns(column).ColumnWidth = width

    sheet.Range("O5:R1004").NumberFormat = '£0.00'
    sheet.Range("S5:S1004").NumberFormat = "0.0%"
    sheet.Range("AB5:AD1004").NumberFormat = '£0.00'
    sheet.Range("AE5:AE1004").NumberFormat = "yyyy-mm-dd hh:mm"
    sheet.Range("AI5:AI1004").NumberFormat = "0.0%"
    sheet.Range("AR5:AR1004").NumberFormat = "yyyy-mm-dd hh:mm"
    sheet.Range("A5:AR1004").VerticalAlignment = XL_TOP
    sheet.Range("E5:AR1004").WrapText = True

    set_validation(
        sheet.Range("AP5:AP1004"),
        [
            "NEW", "CHECKED", "WATCH", "BID",
            "REJECTED", "ENDED",
        ],
    )

    try:
        sheet.Activate()
        workbook.Application.ActiveWindow.FreezePanes = False
        workbook.Application.ActiveWindow.SplitRow = 4
        workbook.Application.ActiveWindow.SplitColumn = 7
        workbook.Application.ActiveWindow.FreezePanes = True
    except Exception:
        pass

    try:
        if sheet.AutoFilterMode:
            sheet.AutoFilterMode = False
        sheet.Range("A4:AR1004").AutoFilter()
    except Exception:
        pass


def setup_archive_sheet(workbook) -> None:
    sheet, _ = get_or_add_sheet(
        workbook,
        "Opportunity Archive",
    )
    sheet.Range("A1:AT3").ClearContents()
    sheet.Range("A1:AT3").ClearFormats()

    style_title(
        sheet,
        46,
        "Opportunity Archive — Historical Live Radar Results",
        (
            "Previous Live Opportunities are appended here before each "
            "successful radar refresh."
        ),
        0x5D3617,
    )

    live_headers = [
        "Rank", "Decision", "Recommended Action", "Score",
        "Discovery Source", "Parent Item ID", "Card Match", "Card ID",
        "Set", "Card Number", "Variant", "Rarity", "Listing Title",
        "Item ID", "Current Bid (£)", "Postage (£)", "Delivered (£)",
        "Market (£)", "Cost / Market", "Direct Listing", "Card Image",
        "Auction Search", "Sold Comparables", "UK Market", "TCGplayer",
        "Cardmarket", "PriceCharting", "Target Delivered (£)",
        "Maximum Bid (£)", "Bid Headroom (£)", "Ends At",
        "Minutes Remaining", "Bid Count", "Seller", "Feedback %",
        "Feedback Count", "Condition", "Condition Flag",
        "Condition Details", "Match Confidence", "Matched Card Search",
        "Status", "Notes", "Last Refreshed",
    ]
    headers = [
        "Archived At",
        "Final Status",
        *live_headers,
    ]
    sheet.Range("A3:AT3").Value = (tuple(headers),)
    style_header(sheet, 3, len(headers), 0x5D3617)


def main() -> int:
    root = Path(__file__).resolve().parent
    load_dotenv(
        root / ".env",
        override=True,
        encoding="utf-8-sig",
    )

    workbook_path = Path(
        os.getenv(
            "WORKBOOK_PATH",
            "Pokemon-Auction-Scanner-Dashboard.xlsx",
        )
    )
    if not workbook_path.is_absolute():
        workbook_path = root / workbook_path

    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Workbook not found: {workbook_path}"
        )

    backup_folder = root / "backups"
    backup_folder.mkdir(exist_ok=True)
    backup_path = backup_folder / (
        f"{workbook_path.stem}-before-live-radar-"
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        f"{workbook_path.suffix}"
    )
    shutil.copy2(workbook_path, backup_path)

    import win32com.client

    excel = win32com.client.DispatchEx(
        "Excel.Application"
    )
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False
    excel.EnableEvents = False

    workbook = excel.Workbooks.Open(
        str(workbook_path.resolve())
    )
    try:
        setup_scanner_settings(workbook)
        setup_live_sheet(workbook)
        setup_archive_sheet(workbook)
        workbook.Save()
    finally:
        workbook.Close(SaveChanges=True)
        excel.EnableEvents = True
        excel.ScreenUpdating = True
        excel.Quit()

    print("LIVE OPPORTUNITY RADAR UPGRADE SUCCESSFUL")
    print(f"Workbook: {workbook_path}")
    print(f"Backup: {backup_path}")
    print("Random Range Sniper sheets and code were not changed.")
    print("Continue using: run-live.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
