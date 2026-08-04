from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from setup_random_range_sniper import (
    get_or_add_sheet,
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
        f"{workbook_path.stem}-before-phase4-1-"
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
        results, _ = get_or_add_sheet(workbook, "Random Snipe Results")

        # Preserve existing settings/history/results while updating labels.
        labels = [
            "Last run",
            "Run ID",
            "Run mode",
            "Eligible pool",
            "Cards attempted",
            "Cards with any live result",
            "All matched live auctions",
            "Random queue rows",
            "Queue GREEN opportunities",
            "Queue AMBER opportunities",
            "eBay API search calls",
            "Run status",
        ]
        for row, label in enumerate(labels, start=4):
            control.Cells(row, 4).Value = label
        control.Range("D4:D15").Interior.Color = 0xD9EAD3
        control.Range("D4:D15").Font.Bold = True
        control.Range("E4:E15").Interior.Color = 0xE2F0D9
        control.Range("E4:E15").Font.Bold = True
        control.Range("F24:F273").NumberFormat = "@"

        results.Cells(2, 1).Value = (
            "All reliably matched live auctions appear here, including "
            "listings outside the configured ending window. Immediate "
            "ending-window findings are copied into Random Snipe Queue. "
            "All listing, active-search, sold and image links are clickable."
        )
        results.Range("G5:G1504").NumberFormat = "@"

        setup_random_queue_sheet(workbook)

        workbook.Save()
    finally:
        workbook.Close(SaveChanges=True)
        excel.EnableEvents = True
        excel.ScreenUpdating = True
        excel.Quit()

    print("PHASE 4.1 UPGRADE SUCCESSFUL")
    print("Fixed whole-number card searches such as 54 instead of 54.0")
    print("Added: Random Snipe Queue")
    print("Random Snipe Results now accepts matches outside the ending window")
    print(f"Backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
