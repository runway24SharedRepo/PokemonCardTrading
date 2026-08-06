from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from ai_review_excel import AIExcelAdapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workbook", default="Pokemon-Auction-Scanner-Dashboard.xlsx"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    workbook = Path(args.workbook)
    if not workbook.is_absolute():
        workbook = root / workbook
    if not workbook.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook}")
    backup_folder = root / "backups" / "phase5.6"
    backup_folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_folder / f"{workbook.stem}-before-ai-review-{stamp}{workbook.suffix}"
    shutil.copy2(workbook, backup)
    excel = AIExcelAdapter(workbook)
    try:
        updated = excel.ensure_all_structure()
        excel.save()
    finally:
        excel.close(save=True)
    print("PHASE 5.6 WORKBOOK UPGRADE SUCCESSFUL")
    print(f"Backup: {backup}")
    print("Added: AI Review Settings and AI Review Log")
    print(f"AI columns checked on {len(updated)} result sheet(s).")
    print("Image processing: DISABLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
