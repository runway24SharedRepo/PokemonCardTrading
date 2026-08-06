from __future__ import annotations

import argparse
import re
import shutil
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


def as_rows(value: Any) -> list[list[Any]]:
    if value is None:
        return []
    if not isinstance(value, tuple):
        return [[value]]
    if value and not isinstance(value[0], tuple):
        return [list(value)]
    return [list(row) for row in value]


def as_text(value: Any) -> str:
    return str(value or "").strip()


def normalise_number(value: Any) -> str:
    raw = as_text(value)
    if not raw:
        return ""
    try:
        parsed = float(raw)
        if parsed.is_integer():
            return str(int(parsed))
    except (TypeError, ValueError):
        pass
    return raw


def positive(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def last_row(sheet, column: int = 1) -> int:
    return max(
        1,
        int(
            sheet.Cells(
                sheet.Rows.Count,
                column,
            ).End(-4162).Row
        ),
    )


def card_key(name: Any, set_name: Any, number: Any):
    return (
        as_text(name).casefold(),
        as_text(set_name).casefold(),
        normalise_number(number).casefold(),
    )


def find_usd_to_gbp_rate(book) -> float:
    try:
        summary = book.Worksheets(
            "Market Update Summary"
        )
        for row in as_rows(
            summary.Range("A1:C50").Value
        ):
            label = as_text(row[0]).casefold()
            if (
                "usd" in label
                and "gbp" in label
                and "rate" in label
            ):
                rate = positive(row[1])
                if rate:
                    return rate
    except Exception:
        pass

    market = book.Worksheets(
        "Market Data Import"
    )
    values = as_rows(
        market.Range(
            f"A5:L{last_row(market, 1)}"
        ).Value
    )
    rates: list[float] = []
    pattern = re.compile(
        r"\bUSD\s+([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )

    for row in values:
        if "TCGplayer" not in as_text(row[8]):
            continue
        current = positive(row[7])
        match = pattern.search(as_text(row[11]))
        original = (
            positive(match.group(1))
            if match
            else None
        )
        if current and original:
            rates.append(current / original)

    if rates:
        return statistics.median(rates)

    raise RuntimeError(
        "USD to GBP rate was not found. Run the market updater once "
        "and retry this repair."
    )


def repair(workbook_path: Path) -> dict[str, int]:
    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Workbook not found: {workbook_path}"
        )

    backup_folder = (
        workbook_path.parent
        / "backups"
        / "phase5.5.3"
    )
    backup_folder.mkdir(
        parents=True,
        exist_ok=True,
    )
    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )
    backup_path = backup_folder / (
        f"{workbook_path.stem}"
        f"-before-edition-price-repair-"
        f"{stamp}{workbook_path.suffix}"
    )
    shutil.copy2(
        workbook_path,
        backup_path,
    )

    import win32com.client

    excel = win32com.client.DispatchEx(
        "Excel.Application"
    )
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False
    excel.EnableEvents = False

    book = excel.Workbooks.Open(
        str(workbook_path.resolve())
    )

    corrected = 0
    disabled = 0
    first_checked = 0
    summaries = 0

    try:
        usd_to_gbp = find_usd_to_gbp_rate(
            book
        )

        database = book.Worksheets(
            "Full Card Database"
        )
        database_values = as_rows(
            database.Range(
                f"A5:AF{last_row(database, 1)}"
            ).Value
        )

        details_by_key: dict[
            tuple[str, str, str],
            dict[str, Any],
        ] = {}

        for row_number, row in enumerate(
            database_values,
            start=5,
        ):
            details_by_key[
                card_key(
                    row[1],
                    row[3],
                    row[5],
                )
            ] = {
                "row": row_number,
                "normal": positive(row[18]),
                "holo": positive(row[19]),
                "reverse": positive(row[20]),
                "first_normal": positive(row[21]),
                "first_holo": positive(row[22]),
                "updated": row[17],
                "url": as_text(row[30]),
            }

        market = book.Worksheets(
            "Market Data Import"
        )
        market_values = as_rows(
            market.Range(
                f"A5:L{last_row(market, 1)}"
            ).Value
        )

        for row_number, row in enumerate(
            market_values,
            start=5,
        ):
            details = details_by_key.get(
                card_key(
                    row[1],
                    row[2],
                    row[3],
                )
            )
            if not details:
                continue

            edition_sensitive = bool(
                details["first_normal"]
                or details["first_holo"]
            )
            if not edition_sensitive:
                continue

            variant = as_text(
                row[4]
            ).casefold()

            raw_usd: float | None = None
            label = ""
            if variant == "normal":
                raw_usd = details["normal"]
                label = "standard/Unlimited Normal"
            elif variant == "holofoil":
                raw_usd = details["holo"]
                label = "standard/Unlimited Holofoil"
            elif variant == "1st edition normal":
                raw_usd = details["first_normal"]
                label = "1st Edition Normal"
                first_checked += 1
            elif variant == "1st edition holofoil":
                raw_usd = details["first_holo"]
                label = "1st Edition Holofoil"
                first_checked += 1
            else:
                continue

            if raw_usd:
                market.Cells(
                    row_number,
                    1,
                ).Value = "YES"
                market.Cells(
                    row_number,
                    8,
                ).Value = round(
                    raw_usd * usd_to_gbp,
                    2,
                )
                market.Cells(
                    row_number,
                    9,
                ).Value = (
                    "Pokémon TCG API / TCGplayer "
                    "(edition-specific)"
                )
                if details["updated"]:
                    market.Cells(
                        row_number,
                        10,
                    ).Value = details["updated"]
                if details["url"]:
                    market.Cells(
                        row_number,
                        11,
                    ).Value = details["url"]
                market.Cells(
                    row_number,
                    12,
                ).Value = (
                    f"USD {raw_usd:.2f}; edition-safe {label} price "
                    f"converted at USD→GBP {usd_to_gbp:.6f}. "
                    "The database reference image is not edition-specific; "
                    "scanner result tabs use the actual eBay listing photo."
                )
                corrected += 1

            elif variant in {
                "normal",
                "holofoil",
            }:
                market.Cells(
                    row_number,
                    1,
                ).Value = "NO"
                market.Cells(
                    row_number,
                    8,
                ).ClearContents()
                market.Cells(
                    row_number,
                    9,
                ).Value = (
                    "DISABLED — edition-safe standard price unavailable"
                )
                market.Cells(
                    row_number,
                    12,
                ).Value = (
                    "A separate First Edition value exists, but no "
                    f"edition-specific {label} value is available. "
                    "Disabled to prevent First Edition overvaluation."
                )
                disabled += 1

        # Refresh Full Card Database summary fields AA:AC with an explicit
        # variant price rather than a broad edition-mixed trend.
        for details in details_by_key.values():
            if not (
                details["first_normal"]
                or details["first_holo"]
            ):
                continue

            choices = [
                ("Normal", details["normal"]),
                ("Holofoil", details["holo"]),
                (
                    "Reverse Holofoil",
                    details["reverse"],
                ),
                (
                    "1st Edition Normal",
                    details["first_normal"],
                ),
                (
                    "1st Edition Holofoil",
                    details["first_holo"],
                ),
            ]
            chosen = next(
                (
                    (variant, value)
                    for variant, value in choices
                    if value
                ),
                None,
            )
            if not chosen:
                continue

            variant, raw_usd = chosen
            row_number = details["row"]
            database.Cells(
                row_number,
                27,
            ).Value = round(
                raw_usd * usd_to_gbp,
                2,
            )
            database.Cells(
                row_number,
                28,
            ).Value = variant
            database.Cells(
                row_number,
                29,
            ).Value = (
                "Pokémon TCG API / TCGplayer "
                "(edition-specific)"
            )
            summaries += 1

        book.Save()

        print("EDITION-SAFE PRICE REPAIR SUCCESSFUL")
        print(f"Workbook backup: {backup_path}")
        print(
            f"USD to GBP rate: "
            f"{usd_to_gbp:.6f}"
        )
        print(
            f"Market rows corrected: "
            f"{corrected}"
        )
        print(
            f"Unsafe standard rows disabled: "
            f"{disabled}"
        )
        print(
            f"First Edition rows checked: "
            f"{first_checked}"
        )
        print(
            f"Full Database summaries refreshed: "
            f"{summaries}"
        )

        return {
            "corrected": corrected,
            "disabled": disabled,
            "first_checked": first_checked,
            "summaries": summaries,
        }

    finally:
        try:
            book.Close(
                SaveChanges=True
            )
        finally:
            excel.Quit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workbook",
        default=(
            "Pokemon-Auction-Scanner-Dashboard.xlsx"
        ),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    workbook = Path(args.workbook)
    if not workbook.is_absolute():
        workbook = root / workbook

    repair(workbook)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
