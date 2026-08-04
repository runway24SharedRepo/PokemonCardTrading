from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from setup_random_range_sniper import (
    get_or_add_sheet,
    set_validation,
    setup_results_sheet,
    setup_random_queue_sheet,
)


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
        f"{workbook_path.stem}-before-phase4-2-"
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
        control, _ = get_or_add_sheet(workbook, "Random Range Sniper")
        control.Cells(21, 1).Value = "Listing formats"
        if control.Cells(21, 2).Value in (None, ""):
            control.Cells(21, 2).Value = "Auctions + Buy It Now"
        control.Range("A21").Interior.Color = 0xE7D3B8
        control.Range("A21").Font.Bold = True
        control.Range("B21").Interior.Color = 0xCCF2FF
        control.Range("B21").Font.Color = 0x0000FF
        set_validation(control.Range("B21"), [
            "Auctions + Buy It Now", "Auctions only", "Buy It Now only",
        ])

        kpi_labels = [
            "Last run", "Run ID", "Run mode", "Eligible pool",
            "Cards attempted", "Cards with any live result",
            "All matched live listings", "Random queue rows",
            "Queue GREEN opportunities", "Queue AMBER opportunities",
            "eBay API search calls", "Run status",
        ]
        for row, label in enumerate(kpi_labels, start=4):
            control.Cells(row, 4).Value = label

        # Update selected-card headers while preserving settings and history.
        selected_headers = [
            "Pick", "Selection Status", "Card ID", "Card Name", "Set",
            "Card Number", "Variant", "Rarity", "Market Value (£)",
            "Target Delivered (£)", "Market Source", "Price Date",
            "Card Image", "Auction Search", "Buy Now Search",
            "Sold Comparables", "Queries Run", "Listings Found",
            "Best Delivered (£)", "Best Discount", "Best Decision",
            "Best Action", "Last Selected", "Notes",
        ]
        control.Range("A23:X273").ClearContents()
        control.Range("A23:X273").ClearFormats()
        control.Range("A23:X23").Value = (tuple(selected_headers),)
        control.Range("A23:X23").Interior.Color = 0x5D3617
        control.Range("A23:X23").Font.Color = 0xFFFFFF
        control.Range("A23:X23").Font.Bold = True
        control.Range("F24:F273").NumberFormat = "@"
        control.Range("I24:J273").NumberFormat = '£0.00'
        control.Range("S24:S273").NumberFormat = '£0.00'
        control.Range("T24:T273").NumberFormat = "0.0%"
        control.Range("W24:W273").NumberFormat = "yyyy-mm-dd hh:mm"
        widths = {
            "A": 7, "B": 22, "C": 17, "D": 25, "E": 25, "F": 12,
            "G": 22, "H": 20, "I": 15, "J": 17, "K": 29, "L": 14,
            "M": 18, "N": 20, "O": 19, "P": 20, "Q": 12, "R": 14,
            "S": 16, "T": 14, "U": 14, "V": 22, "W": 18, "X": 45,
        }
        for column, width in widths.items():
            control.Columns(column).ColumnWidth = width
        try:
            if control.AutoFilterMode:
                control.AutoFilterMode = False
            control.Range("A23:X273").AutoFilter()
        except Exception:
            pass

        # Results and queue are run outputs, so rebuild their layouts cleanly.
        setup_results_sheet(workbook)
        setup_random_queue_sheet(workbook)
        workbook.Save()
    finally:
        workbook.Close(SaveChanges=True)
        excel.EnableEvents = True
        excel.ScreenUpdating = True
        excel.Quit()

    print("PHASE 4.2 UPGRADE SUCCESSFUL")
    print("Decision cells now use real GREEN/AMBER/RED fills.")
    print("Auction bids and Buy It Now prices are evaluated separately.")
    print("Added Listing formats control and separate search links.")
    print(f"Backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
