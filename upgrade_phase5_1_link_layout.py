from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from setup_live_opportunity_radar import (
    get_or_add_sheet as get_or_add_live_sheet,
    setup_archive_sheet,
    setup_live_sheet,
)
from setup_random_range_sniper import (
    setup_random_queue_sheet,
    setup_results_sheet,
)


def unique_sheet_name(workbook, base: str) -> str:
    existing = {
        str(workbook.Worksheets(index).Name).casefold()
        for index in range(1, workbook.Worksheets.Count + 1)
    }
    if base.casefold() not in existing:
        return base

    counter = 2
    while f"{base} {counter}".casefold() in existing:
        counter += 1
    return f"{base} {counter}"


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
        f"{workbook_path.stem}-before-phase5-1-layout-"
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
        # Preserve any existing archive by moving it to a legacy sheet,
        # because the new archive column order follows the new link layout.
        try:
            archive = workbook.Worksheets(
                "Opportunity Archive"
            )
            last_row = int(
                archive.Cells(
                    archive.Rows.Count,
                    1,
                ).End(-4162).Row
            )
            if last_row > 3:
                archive.Name = unique_sheet_name(
                    workbook,
                    "Opportunity Archive Legacy",
                )
        except Exception:
            pass

        # Results are transient and will be repopulated on the next scan.
        setup_results_sheet(workbook)
        setup_random_queue_sheet(workbook)
        setup_live_sheet(workbook)
        setup_archive_sheet(workbook)

        workbook.Save()
    finally:
        workbook.Close(SaveChanges=True)
        excel.EnableEvents = True
        excel.ScreenUpdating = True
        excel.Quit()

    print("PHASE 5.1 LINK-LAYOUT UPGRADE SUCCESSFUL")
    print("Updated:")
    print("  - Random Snipe Results")
    print("  - Random Snipe Queue")
    print("  - Live Opportunities")
    print("Links now sit beside the market-ratio columns.")
    print("Random Snipe History and all market data were preserved.")
    print(f"Workbook backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
