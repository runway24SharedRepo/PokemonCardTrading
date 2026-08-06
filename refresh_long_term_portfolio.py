from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

from long_term_excel import LongTermWorkbookManager
from upgrade_phase5_5_long_term_investment import database_index, market_index


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

    import win32com.client

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False
    excel.EnableEvents = False
    workbook = excel.Workbooks.Open(str(workbook_path.resolve()))

    try:
        manager = LongTermWorkbookManager(workbook)
        manager.ensure_sheets()
        _, db_by_fields = database_index(workbook)
        markets = market_index(workbook)
        candidates = []
        for (name_key, set_key, number_key, variant), market in markets.items():
            details = db_by_fields.get(
                (name_key, set_key, number_key),
                {
                    "card_id": "",
                    "name": name_key,
                    "set_name": set_key,
                    "number": number_key,
                    "rarity": "",
                    "supertype": "",
                    "release_date": None,
                },
            )
            candidates.append(
                SimpleNamespace(
                    card_id=details.get("card_id", ""),
                    name=details.get("name", name_key),
                    set_name=details.get("set_name", set_key),
                    number=details.get("number", number_key),
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
            )

        updated = manager.refresh_portfolio(candidates)
        manager.refresh_dashboard()
        workbook.Save()
    finally:
        workbook.Close(SaveChanges=True)
        excel.EnableEvents = True
        excel.ScreenUpdating = True
        excel.Quit()

    print("LONG-TERM PORTFOLIO REFRESH SUCCESSFUL")
    print(f"Portfolio rows refreshed: {updated}")
    print("Long-Term Dashboard refreshed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
