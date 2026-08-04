from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


XL_CENTER = -4108
XL_TOP = -4160
XL_SHEET_HIDDEN = 0


def get_or_add_sheet(workbook, name: str):
    try:
        return workbook.Worksheets(name), False
    except Exception:
        sheet = workbook.Worksheets.Add(
            After=workbook.Worksheets(workbook.Worksheets.Count)
        )
        sheet.Name = name
        return sheet, True


def set_validation(cell_range, values: list[str]) -> None:
    try:
        cell_range.Validation.Delete()
    except Exception:
        pass
    formula = ",".join(values)
    cell_range.Validation.Add(
        Type=3,
        AlertStyle=1,
        Operator=1,
        Formula1=formula,
    )
    cell_range.Validation.IgnoreBlank = True
    cell_range.Validation.InCellDropdown = True


def apply_title(sheet, last_column: int, title: str, description: str, fill: int) -> None:
    sheet.Cells(1, 1).Value = title
    sheet.Cells(2, 1).Value = description
    sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Interior.Color = fill
    sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Font.Color = 0xFFFFFF
    sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Font.Bold = True
    sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, last_column)).Font.Size = 17
    sheet.Range(sheet.Cells(2, 1), sheet.Cells(2, last_column)).Interior.Color = 0xF7EAD9
    sheet.Range(sheet.Cells(2, 1), sheet.Cells(2, last_column)).WrapText = True
    sheet.Rows(1).RowHeight = 30
    sheet.Rows(2).RowHeight = 38


def apply_header(sheet, row: int, columns: int, fill: int) -> None:
    header = sheet.Range(sheet.Cells(row, 1), sheet.Cells(row, columns))
    header.Interior.Color = fill
    header.Font.Color = 0xFFFFFF
    header.Font.Bold = True
    header.HorizontalAlignment = XL_CENTER
    header.VerticalAlignment = XL_CENTER
    header.WrapText = True
    sheet.Rows(row).RowHeight = 44


def format_all_borders(sheet, address: str) -> None:
    rng = sheet.Range(address)
    for edge in range(7, 13):
        try:
            rng.Borders(edge).LineStyle = 1
            rng.Borders(edge).Color = 0xD9D9D9
            rng.Borders(edge).Weight = 2
        except Exception:
            pass


def setup_control_sheet(workbook):
    sheet, created = get_or_add_sheet(workbook, "Random Range Sniper")
    if created:
        sheet.Cells.Clear()

    apply_title(
        sheet,
        22,
        "Random Range Sniper — Smart Card Opportunity Generator",
        (
            "Choose a GBP market range and run the batch file. The system "
            "randomly selects exact card variants, searches UK eBay auctions, "
            "and creates clickable active, sold, listing and image links."
        ),
        0x5D3617,
    )

    controls = [
        ("Minimum market value (£)", 5.00),
        ("Maximum market value (£)", 40.00),
        ("Number of cards", 20),
        ("Selection mode", "Smart Random"),
        ("Card category", "Pokémon only"),
        ("Variant selection", "Any"),
        ("One variant per card", "YES"),
        ("Avoid recent repeats", "14 days"),
        ("Replace cards with no auctions", "YES"),
        ("Search depth", "Balanced"),
        ("Target purchase ratio", "75%"),
        ("Ending within", "24 hours"),
        ("Minimum seller feedback", "98%"),
        ("Maximum postage", "Any"),
        ("Copy GREEN to Snipe Queue", "YES"),
        ("Maximum card attempts", 60),
        ("Random seed", ""),
    ]

    for index, (label, default) in enumerate(controls, start=4):
        sheet.Cells(index, 1).Value = label
        if created or sheet.Cells(index, 2).Value in (None, ""):
            sheet.Cells(index, 2).Value = default

    sheet.Range("A4:A20").Interior.Color = 0xE7D3B8
    sheet.Range("A4:A20").Font.Bold = True
    sheet.Range("B4:B20").Interior.Color = 0xCCF2FF
    sheet.Range("B4:B20").Font.Color = 0x0000FF
    sheet.Range("B4:B5").NumberFormat = '£0.00'
    sheet.Range("B14:B14").NumberFormat = "0%"

    set_validation(sheet.Range("B6"), ["5", "10", "15", "20", "25", "30", "40", "50"])
    set_validation(sheet.Range("B7"), [
        "Smart Random", "Pure Random", "Never Scanned First",
        "No Recent Repeats", "Previously Successful", "Rising Market",
        "Vintage Random", "Modern Random",
    ])
    set_validation(sheet.Range("B8"), [
        "Pokémon only", "Trainer only", "Energy only",
        "Pokémon + Trainer", "All cards",
    ])
    set_validation(sheet.Range("B9"), [
        "Any", "Normal", "Holo", "Reverse Holo", "First Edition",
    ])
    set_validation(sheet.Range("B10"), ["YES", "NO"])
    set_validation(sheet.Range("B11"), [
        "No cooldown", "1 day", "7 days", "14 days", "30 days",
        "90 days", "Never repeat until pool exhausted",
    ])
    set_validation(sheet.Range("B12"), ["YES", "NO"])
    set_validation(sheet.Range("B13"), ["Fast", "Balanced", "Deep"])
    set_validation(sheet.Range("B14"), [
        "60%", "65%", "70%", "75%", "80%", "85%", "90%",
    ])
    set_validation(sheet.Range("B15"), [
        "30 minutes", "1 hour", "2 hours", "6 hours",
        "12 hours", "24 hours", "48 hours", "7 days",
    ])
    set_validation(sheet.Range("B16"), [
        "100%", "99.5%", "99%", "98%", "97%", "95%",
    ])
    set_validation(sheet.Range("B17"), [
        "Any", "£1", "£2", "£3", "£5", "£10",
    ])
    set_validation(sheet.Range("B18"), ["YES", "NO"])

    kpi_labels = [
        "Last run",
        "Run ID",
        "Run mode",
        "Eligible pool",
        "Cards attempted",
        "Cards with results",
        "All matched live auctions",
        "Random queue rows",
        "Queue GREEN opportunities",
        "Queue AMBER opportunities",
        "eBay API search calls",
        "Run status",
    ]
    sheet.Range("D3:E3").Value = (("Latest Run Summary", "Value"),)
    sheet.Range("D3:E3").Interior.Color = 0x006100
    sheet.Range("D3:E3").Font.Color = 0xFFFFFF
    sheet.Range("D3:E3").Font.Bold = True

    for row, label in enumerate(kpi_labels, start=4):
        sheet.Cells(row, 4).Value = label
    sheet.Range("D4:D15").Interior.Color = 0xD9EAD3
    sheet.Range("D4:D15").Font.Bold = True
    sheet.Range("E4:E15").Interior.Color = 0xE2F0D9
    sheet.Range("E4:E15").Font.Bold = True
    sheet.Range("E4").NumberFormat = "yyyy-mm-dd hh:mm"

    instructions = [
        ("Normal workflow", "Set min/max/count → save and close Excel → run run-random-range-sniper.bat"),
        ("Reroll only", "Run reroll-random-cards-only.bat to choose cards without API calls"),
        ("Best default", "Smart Random, Pokémon only, 14-day cooldown, Balanced, 75%"),
        ("Safety", "Always inspect photographs and never exceed Maximum Bid"),
    ]
    sheet.Range("G3:H3").Value = (("Quick Guide", "Instruction"),)
    sheet.Range("G3:H3").Interior.Color = 0x17365D
    sheet.Range("G3:H3").Font.Color = 0xFFFFFF
    sheet.Range("G3:H3").Font.Bold = True
    for row, item in enumerate(instructions, start=4):
        sheet.Range(f"G{row}:H{row}").Value = (item,)
    sheet.Range("G4:G7").Interior.Color = 0xD9EAF7
    sheet.Range("G4:G7").Font.Bold = True
    sheet.Range("H4:H7").WrapText = True

    headers = [
        "Pick", "Selection Status", "Card ID", "Card Name", "Set",
        "Card Number", "Variant", "Rarity", "Market Value (£)",
        "Target Delivered (£)", "Market Source", "Price Date",
        "Card Image", "Active eBay Search", "Sold Comparables",
        "Queries Run", "Listings Found", "Best Delivered (£)",
        "Best Discount", "Best Decision", "Last Selected", "Notes",
    ]
    sheet.Range("A23:V23").Value = (tuple(headers),)
    apply_header(sheet, 23, len(headers), 0x5D3617)
    format_all_borders(sheet, "A23:V273")

    widths = {
        "A": 7, "B": 22, "C": 17, "D": 25, "E": 25, "F": 12,
        "G": 22, "H": 20, "I": 15, "J": 17, "K": 29, "L": 14,
        "M": 18, "N": 21, "O": 20, "P": 12, "Q": 14, "R": 16,
        "S": 14, "T": 14, "U": 18, "V": 45,
    }
    for column, width in widths.items():
        sheet.Columns(column).ColumnWidth = width

    sheet.Range("F24:F273").NumberFormat = "@"
    sheet.Range("I24:J273").NumberFormat = '£0.00'
    sheet.Range("R24:R273").NumberFormat = '£0.00'
    sheet.Range("S24:S273").NumberFormat = "0.0%"
    sheet.Range("L24:L273").NumberFormat = "yyyy-mm-dd"
    sheet.Range("U24:U273").NumberFormat = "yyyy-mm-dd hh:mm"
    sheet.Range("A24:V273").VerticalAlignment = XL_TOP
    sheet.Range("B24:V273").WrapText = True

    try:
        sheet.Activate()
        workbook.Application.ActiveWindow.FreezePanes = False
        workbook.Application.ActiveWindow.SplitRow = 23
        workbook.Application.ActiveWindow.SplitColumn = 2
        workbook.Application.ActiveWindow.FreezePanes = True
    except Exception:
        pass

    try:
        sheet.Range("A23:V273").AutoFilter()
    except Exception:
        pass


def setup_results_sheet(workbook):
    sheet, created = get_or_add_sheet(workbook, "Random Snipe Results")
    if created:
        sheet.Cells.Clear()

    apply_title(
        sheet,
        33,
        "Random Snipe Results — Live UK eBay Auctions",
        (
            "All reliably matched live auctions appear here, including "
            "listings outside the configured ending window. Immediate "
            "ending-window findings are copied into Random Snipe Queue. "
            "All links are clickable."
        ),
        0x006100,
    )

    headers = [
        "Rank", "Decision", "Score", "Selected Card", "Card ID", "Set",
        "Card Number", "Variant", "Listing Title", "Item ID",
        "Current Bid (£)", "Postage (£)", "Delivered (£)", "Market (£)",
        "Cost / Market", "Target Delivered (£)", "Maximum Bid (£)",
        "Bid Headroom (£)", "Ends At", "Minutes Remaining", "Bid Count",
        "Seller", "Feedback %", "Feedback Count", "Condition",
        "Match Confidence", "Search Query", "Direct Listing",
        "Active Search", "Sold Comparables", "Card Image", "Status", "Notes",
    ]
    sheet.Range("A4:AG4").Value = (tuple(headers),)
    apply_header(sheet, 4, len(headers), 0x006100)
    format_all_borders(sheet, "A4:AG1504")

    widths = {
        "A": 7, "B": 11, "C": 9, "D": 40, "E": 17, "F": 24,
        "G": 12, "H": 22, "I": 50, "J": 20, "K": 13, "L": 11,
        "M": 13, "N": 12, "O": 13, "P": 17, "Q": 15, "R": 15,
        "S": 18, "T": 16, "U": 10, "V": 18, "W": 12, "X": 14,
        "Y": 17, "Z": 16, "AA": 35, "AB": 17, "AC": 19,
        "AD": 20, "AE": 18, "AF": 12, "AG": 45,
    }
    for column, width in widths.items():
        sheet.Columns(column).ColumnWidth = width

    sheet.Range("K5:N1504").NumberFormat = '£0.00'
    sheet.Range("O5:O1504").NumberFormat = "0.0%"
    sheet.Range("P5:R1504").NumberFormat = '£0.00'
    sheet.Range("S5:S1504").NumberFormat = "yyyy-mm-dd hh:mm"
    sheet.Range("W5:W1504").NumberFormat = "0.0%"
    sheet.Range("A5:AG1504").VerticalAlignment = XL_TOP
    sheet.Range("D5:AG1504").WrapText = True

    set_validation(sheet.Range("AF5:AF1504"), [
        "NEW", "CHECKED", "WATCH", "BID", "REJECTED", "ENDED",
    ])

    try:
        sheet.Activate()
        workbook.Application.ActiveWindow.FreezePanes = False
        workbook.Application.ActiveWindow.SplitRow = 4
        workbook.Application.ActiveWindow.SplitColumn = 3
        workbook.Application.ActiveWindow.FreezePanes = True
    except Exception:
        pass

    try:
        sheet.Range("A4:AG1504").AutoFilter()
    except Exception:
        pass



def setup_random_queue_sheet(workbook):
    sheet, created = get_or_add_sheet(workbook, "Random Snipe Queue")
    if created:
        sheet.Cells.Clear()

    apply_title(
        sheet,
        28,
        "Random Snipe Queue — Auctions Inside Your Ending Window",
        (
            "This is the immediate-action subset of Random Snipe Results. "
            "It contains matched UK auctions ending within the configured "
            "window, with clickable listing, active-search, sold and image links."
        ),
        0x9C6500,
    )

    headers = [
        "Priority", "Decision", "Score", "Selected Card", "Card ID",
        "Listing Title", "Current Bid (£)", "Postage (£)", "Delivered (£)",
        "Market (£)", "Cost / Market", "Target Delivered (£)",
        "Maximum Bid (£)", "Bid Headroom (£)", "Ends At",
        "Minutes Remaining", "Bid Count", "Seller", "Feedback %",
        "Condition", "Match Confidence", "Search Query", "Direct Listing",
        "Active Search", "Sold Comparables", "Card Image", "Status", "Notes",
    ]
    sheet.Range("A4:AB4").Value = (tuple(headers),)
    apply_header(sheet, 4, len(headers), 0x9C6500)
    format_all_borders(sheet, "A4:AB1504")

    widths = {
        "A": 9, "B": 11, "C": 9, "D": 40, "E": 17, "F": 50,
        "G": 13, "H": 11, "I": 13, "J": 12, "K": 13, "L": 17,
        "M": 15, "N": 15, "O": 18, "P": 16, "Q": 10, "R": 18,
        "S": 12, "T": 17, "U": 16, "V": 35, "W": 17, "X": 19,
        "Y": 20, "Z": 18, "AA": 12, "AB": 48,
    }
    for column, width in widths.items():
        sheet.Columns(column).ColumnWidth = width

    sheet.Range("G5:J1504").NumberFormat = '£0.00'
    sheet.Range("K5:K1504").NumberFormat = "0.0%"
    sheet.Range("L5:N1504").NumberFormat = '£0.00'
    sheet.Range("O5:O1504").NumberFormat = "yyyy-mm-dd hh:mm"
    sheet.Range("S5:S1504").NumberFormat = "0.0%"
    sheet.Range("A5:AB1504").VerticalAlignment = XL_TOP
    sheet.Range("D5:AB1504").WrapText = True

    set_validation(sheet.Range("AA5:AA1504"), [
        "NEW", "CHECKED", "WATCH", "BID", "REJECTED", "ENDED",
    ])

    try:
        sheet.Activate()
        workbook.Application.ActiveWindow.FreezePanes = False
        workbook.Application.ActiveWindow.SplitRow = 4
        workbook.Application.ActiveWindow.SplitColumn = 3
        workbook.Application.ActiveWindow.FreezePanes = True
    except Exception:
        pass

    try:
        sheet.Range("A4:AB1504").AutoFilter()
    except Exception:
        pass


def setup_history_sheet(workbook):
    sheet, created = get_or_add_sheet(workbook, "Random Snipe History")
    if created:
        sheet.Cells.Clear()

    apply_title(
        sheet,
        23,
        "Random Snipe History — Rotation and Performance",
        (
            "Append-only history used for repeat avoidance, never-scanned "
            "selection and previously-successful selection modes."
        ),
        0x17365D,
    )

    headers = [
        "Run ID", "Run Time", "Selection Order", "Card ID", "Card Name",
        "Set", "Card Number", "Variant", "Market (£)", "Selection Mode",
        "Minimum (£)", "Maximum (£)", "Search Depth", "Queries Run",
        "Listings Found", "GREEN", "AMBER", "RED", "Best Delivered (£)",
        "Best Discount", "Outcome", "Active Search", "Sold Comparables",
    ]
    sheet.Range("A4:W4").Value = (tuple(headers),)
    apply_header(sheet, 4, len(headers), 0x17365D)
    format_all_borders(sheet, "A4:W50004")

    widths = {
        "A": 25, "B": 19, "C": 13, "D": 17, "E": 24, "F": 24,
        "G": 12, "H": 22, "I": 12, "J": 24, "K": 12, "L": 12,
        "M": 14, "N": 12, "O": 14, "P": 10, "Q": 10, "R": 10,
        "S": 16, "T": 14, "U": 22, "V": 19, "W": 20,
    }
    for column, width in widths.items():
        sheet.Columns(column).ColumnWidth = width

    sheet.Range("B5:B50004").NumberFormat = "yyyy-mm-dd hh:mm"
    sheet.Range("I5:I50004").NumberFormat = '£0.00'
    sheet.Range("K5:L50004").NumberFormat = '£0.00'
    sheet.Range("S5:S50004").NumberFormat = '£0.00'
    sheet.Range("T5:T50004").NumberFormat = "0.0%"
    sheet.Range("A5:W50004").VerticalAlignment = XL_TOP
    sheet.Range("D5:W50004").WrapText = True

    try:
        sheet.Activate()
        workbook.Application.ActiveWindow.FreezePanes = False
        workbook.Application.ActiveWindow.SplitRow = 4
        workbook.Application.ActiveWindow.FreezePanes = True
    except Exception:
        pass

    try:
        sheet.Range("A4:W50004").AutoFilter()
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
        raise FileNotFoundError(
            f"Workbook not found: {workbook_path}"
        )

    backup_folder = root / "backups"
    backup_folder.mkdir(exist_ok=True)
    backup_path = backup_folder / (
        f"{workbook_path.stem}-before-random-sniper-"
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
    try:
        setup_control_sheet(workbook)
        setup_results_sheet(workbook)
        setup_random_queue_sheet(workbook)
        setup_history_sheet(workbook)
        workbook.Save()
    finally:
        workbook.Close(SaveChanges=True)
        excel.EnableEvents = True
        excel.ScreenUpdating = True
        excel.Quit()

    print("PHASE 4 WORKBOOK INSTALLATION SUCCESSFUL")
    print(f"Workbook: {workbook_path}")
    print(f"Backup: {backup_path}")
    print("New sheets:")
    print("  - Random Range Sniper")
    print("  - Random Snipe Results")
    print("  - Random Snipe Queue")
    print("  - Random Snipe History")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
