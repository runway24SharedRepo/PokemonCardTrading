from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from market_price_controls import (
    ensure_controls_sheet,
    read_controls,
)


XL_UP = -4162
XL_CALCULATION_MANUAL = -4135


def progress(message: str) -> None:
    print(message, flush=True)


def text(value: Any) -> str:
    return str(value or "").strip()


def positive(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def normal_number(value: Any) -> str:
    raw = text(value)
    try:
        parsed = float(raw)
        if parsed.is_integer():
            return str(int(parsed))
    except (TypeError, ValueError):
        pass
    return raw


def as_rows(
    value: Any,
    expected_columns: int | None = None,
) -> list[list[Any]]:
    if value is None:
        output: list[list[Any]] = []
    elif not isinstance(value, tuple):
        output = [[value]]
    elif value and not isinstance(value[0], tuple):
        output = [list(value)]
    else:
        output = [list(row) for row in value]

    if expected_columns is not None:
        for row in output:
            if len(row) < expected_columns:
                row.extend(
                    [None]
                    * (expected_columns - len(row))
                )
            elif len(row) > expected_columns:
                del row[expected_columns:]
    return output


def last_row(sheet, column: int = 1) -> int:
    return max(
        1,
        int(
            sheet.Cells(
                sheet.Rows.Count,
                column,
            ).End(XL_UP).Row
        ),
    )


def card_key(
    name: Any,
    set_name: Any,
    number: Any,
) -> tuple[str, str, str]:
    return (
        text(name).casefold(),
        text(set_name).casefold(),
        normal_number(number).casefold(),
    )


def fx_rates(workbook) -> tuple[float, float]:
    summary = workbook.Worksheets(
        "Market Update Summary"
    )
    values = as_rows(
        summary.Range("A4:B30").Value,
        expected_columns=2,
    )

    eur = None
    usd = None
    for row in values:
        label = text(row[0]).casefold()
        value = positive(row[1])
        if value is None:
            continue
        if "eur" in label and "gbp" in label:
            eur = value
        if "usd" in label and "gbp" in label:
            usd = value

    if eur is None or usd is None:
        raise RuntimeError(
            "FX rates were not found in Market Update Summary. "
            "Run update-pokemon-market-daily.bat once, close Excel, "
            "then retry this hotfix."
        )
    return eur, usd


def choose_base(
    details: dict[str, Any],
    variant: str,
    eur_to_gbp: float,
    usd_to_gbp: float,
) -> tuple[
    float | None,
    str,
    str,
    str,
]:
    variant_key = variant.strip().casefold()

    tcg_field = {
        "normal": "normal",
        "holofoil": "holo",
        "reverse holofoil": "reverse",
        "1st edition normal": "first_normal",
        "1st edition holofoil": "first_holo",
    }.get(variant_key)

    if tcg_field:
        raw = positive(details.get(tcg_field))
        if raw is not None:
            return (
                round(raw * usd_to_gbp, 2),
                (
                    "Pokémon TCG API / "
                    "TCGplayer (primary market)"
                ),
                "TCGPLAYER PRIMARY",
                (
                    f"USD {raw:.2f} market; "
                    "converted to GBP."
                ),
            )

    if variant_key == "normal":
        raw = positive(details.get("cm_normal"))
        if raw is not None:
            return (
                round(raw * eur_to_gbp, 2),
                (
                    "Pokémon TCG API / "
                    "Cardmarket (fallback trend)"
                ),
                "CARDMARKET FALLBACK",
                (
                    f"EUR {raw:.2f} trend; "
                    "used only because TCGplayer "
                    "Normal market was unavailable."
                ),
            )

    if variant_key == "reverse holofoil":
        raw = positive(details.get("cm_reverse"))
        if raw is not None:
            return (
                round(raw * eur_to_gbp, 2),
                (
                    "Pokémon TCG API / "
                    "Cardmarket (fallback trend)"
                ),
                "CARDMARKET FALLBACK",
                (
                    f"EUR {raw:.2f} reverse trend; "
                    "used only because TCGplayer "
                    "Reverse market was unavailable."
                ),
            )

    return (
        None,
        "",
        "UNVERIFIED",
        "No exact variant market value was available.",
    )


def build_database_index(
    database_rows: list[list[Any]],
) -> dict[
    tuple[str, str, str],
    dict[str, Any],
]:
    details_by_key: dict[
        tuple[str, str, str],
        dict[str, Any],
    ] = {}

    for row in database_rows:
        if len(row) < 31:
            continue

        details_by_key[
            card_key(
                row[1],
                row[3],
                row[5],
            )
        ] = {
            "card_id": text(row[0]),
            "normal": row[18],
            "holo": row[19],
            "reverse": row[20],
            "first_normal": row[21],
            "first_holo": row[22],
            "cm_normal": row[24],
            "cm_reverse": row[25],
            "source_date": (
                row[17] or row[23]
            ),
            "source_url": text(row[30]),
        }

    return details_by_key


def repair_market_matrix(
    market_rows: list[list[Any]],
    details_by_key: dict[
        tuple[str, str, str],
        dict[str, Any],
    ],
    controls: dict[Any, Any],
    eur_to_gbp: float,
    usd_to_gbp: float,
    now: datetime,
) -> tuple[list[list[Any]], dict[str, int]]:
    corrected = 0
    overrides_applied = 0
    fallback_rows = 0
    unverified = 0

    for row in market_rows:
        if len(row) < 19:
            row.extend([None] * (19 - len(row)))

        name = text(row[1])
        set_name = text(row[2])
        number = text(row[3])
        variant = text(row[4])

        if not name or not set_name or not number or not variant:
            continue

        details = details_by_key.get(
            card_key(name, set_name, number)
        )
        if not details:
            row[17] = "UNVERIFIED — CARD NOT FOUND"
            row[18] = now
            unverified += 1
            continue

        (
            base_value,
            base_source,
            status,
            note,
        ) = choose_base(
            details,
            variant,
            eur_to_gbp,
            usd_to_gbp,
        )

        card_id = details["card_id"]
        control = controls.get(
            (
                card_id.casefold(),
                variant.casefold(),
            )
        )

        effective_value = base_value
        effective_source = base_source
        effective_url = details["source_url"]
        effective_date = details["source_date"]
        override_value: Any = ""
        override_source = ""

        if control is not None:
            effective_value = (
                control.override_value_gbp
            )
            effective_source = (
                control.override_source
            )
            effective_url = (
                control.source_url
                or effective_url
            )
            effective_date = (
                control.source_date
                or effective_date
            )
            override_value = (
                control.override_value_gbp
            )
            override_source = (
                control.override_source
            )
            status = (
                "PRICECHARTING OVERRIDE"
                if "pricecharting"
                in control.override_source.casefold()
                else "VERIFIED OVERRIDE"
            )
            note = (
                f"Override replaces base "
                f"{base_source or 'unavailable'} value "
                f"{'£' + format(base_value, '.2f') if base_value else 'N/A'}. "
                f"{control.notes}"
            ).strip()
            overrides_applied += 1

        if effective_value is None:
            row[0] = "NO"
            row[7] = None
            row[8] = (
                "DISABLED — exact market "
                "value unavailable"
            )
            row[9] = effective_date
            row[10] = effective_url
            row[11] = note
            unverified += 1
        else:
            row[0] = "YES"
            row[7] = effective_value
            row[8] = effective_source
            row[9] = effective_date
            row[10] = effective_url
            row[11] = note
            corrected += 1

        if status == "CARDMARKET FALLBACK":
            fallback_rows += 1

        row[12] = card_id
        row[13] = (
            base_value
            if base_value is not None
            else None
        )
        row[14] = base_source
        row[15] = override_value
        row[16] = override_source
        row[17] = status
        row[18] = now

    return market_rows, {
        "corrected": corrected,
        "overrides": overrides_applied,
        "fallbacks": fallback_rows,
        "unverified": unverified,
    }


def repair(
    workbook_path: Path,
) -> dict[str, int]:
    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Workbook not found: {workbook_path}"
        )

    progress(
        "[1/8] Preparing timestamped workbook backup..."
    )
    backup_folder = (
        workbook_path.parent
        / "backups"
        / "phase5.6.1.1"
    )
    backup_folder.mkdir(
        parents=True,
        exist_ok=True,
    )
    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )
    backup = backup_folder / (
        f"{workbook_path.stem}"
        f"-before-fast-market-repair-"
        f"{stamp}{workbook_path.suffix}"
    )
    shutil.copy2(
        workbook_path,
        backup,
    )
    progress(
        f"      Backup created: {backup.name}"
    )

    progress(
        "[2/8] Starting a private Excel process..."
    )
    import win32com.client

    excel = win32com.client.DispatchEx(
        "Excel.Application"
    )
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.AskToUpdateLinks = False
    excel.ScreenUpdating = False
    excel.EnableEvents = False

    book = None
    old_calculation = None

    try:
        progress(
            "[3/8] Opening the workbook without updating links..."
        )
        book = excel.Workbooks.Open(
            Filename=str(
                workbook_path.resolve()
            ),
            UpdateLinks=0,
            ReadOnly=False,
            IgnoreReadOnlyRecommended=True,
            Notify=False,
            AddToMru=False,
        )
        try:
            old_calculation = excel.Calculation
            excel.Calculation = (
                XL_CALCULATION_MANUAL
            )
        except Exception:
            old_calculation = None

        progress(
            "[4/8] Reading price controls and FX rates..."
        )
        ensure_controls_sheet(book)
        controls = read_controls(book)
        eur_to_gbp, usd_to_gbp = fx_rates(
            book
        )
        progress(
            f"      Controls loaded: {len(controls):,}"
        )
        progress(
            f"      EUR→GBP: {eur_to_gbp:.6f} | "
            f"USD→GBP: {usd_to_gbp:.6f}"
        )

        progress(
            "[5/8] Loading Full Card Database..."
        )
        database = book.Worksheets(
            "Full Card Database"
        )
        database_end = last_row(
            database,
            1,
        )
        database_rows = as_rows(
            database.Range(
                f"A5:AF{database_end}"
            ).Value,
            expected_columns=32,
        )
        details_by_key = build_database_index(
            database_rows
        )
        progress(
            f"      Database rows read: "
            f"{len(database_rows):,}"
        )
        progress(
            f"      Indexed identities: "
            f"{len(details_by_key):,}"
        )

        progress(
            "[6/8] Recalculating Market Data Import in memory..."
        )
        market = book.Worksheets(
            "Market Data Import"
        )
        market_end = last_row(
            market,
            1,
        )

        extra_headers = [
            "Card ID",
            "Base Imported Value (£)",
            "Base Imported Source",
            "Override Value (£)",
            "Override Source",
            "Price Status",
            "Last Synced",
        ]
        market.Range("M4:S4").Value = (
            tuple(extra_headers),
        )
        market.Range(
            "M4:S4"
        ).Interior.Color = 0x5D3617
        market.Range(
            "M4:S4"
        ).Font.Color = 0xFFFFFF
        market.Range(
            "M4:S4"
        ).Font.Bold = True
        market.Range(
            "M4:S4"
        ).WrapText = True

        market_rows = as_rows(
            market.Range(
                f"A5:S{market_end}"
            ).Value,
            expected_columns=19,
        )
        progress(
            f"      Market rows read: "
            f"{len(market_rows):,}"
        )

        market_rows, statistics = (
            repair_market_matrix(
                market_rows,
                details_by_key,
                controls,
                eur_to_gbp,
                usd_to_gbp,
                datetime.now(),
            )
        )

        progress(
            "[7/8] Writing all corrected values to Excel in one bulk operation..."
        )
        if market_rows:
            market.Range(
                f"A5:S{market_end}"
            ).Value = tuple(
                tuple(row)
                for row in market_rows
            )

        market.Columns("M").ColumnWidth = 18
        market.Columns("N").ColumnWidth = 20
        market.Columns("O").ColumnWidth = 34
        market.Columns("P").ColumnWidth = 18
        market.Columns("Q").ColumnWidth = 25
        market.Columns("R").ColumnWidth = 23
        market.Columns("S").ColumnWidth = 20
        market.Range(
            f"N5:N{market_end}"
        ).NumberFormat = "£0.00"
        market.Range(
            f"P5:P{market_end}"
        ).NumberFormat = "£0.00"
        market.Range(
            f"S5:S{market_end}"
        ).NumberFormat = (
            "yyyy-mm-dd hh:mm"
        )

        progress(
            "[8/8] Saving the workbook..."
        )
        book.Save()

        progress("")
        progress(
            "MARKET VALUE AUTHORITY FAST REPAIR SUCCESSFUL"
        )
        progress(
            f"Workbook backup: {backup}"
        )
        progress(
            f"Rows recalculated: "
            f"{statistics['corrected']:,}"
        )
        progress(
            f"Verified overrides applied: "
            f"{statistics['overrides']:,}"
        )
        progress(
            f"Cardmarket fallback rows: "
            f"{statistics['fallbacks']:,}"
        )
        progress(
            f"Disabled/unverified rows: "
            f"{statistics['unverified']:,}"
        )
        progress(
            "Market Data Import column H remains authoritative."
        )
        return statistics

    finally:
        if book is not None:
            try:
                book.Close(
                    SaveChanges=True
                )
            except Exception:
                pass

        if (
            old_calculation is not None
        ):
            try:
                excel.Calculation = (
                    old_calculation
                )
            except Exception:
                pass

        try:
            excel.Quit()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workbook",
        default=(
            "Pokemon-Auction-Scanner-"
            "Dashboard.xlsx"
        ),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    workbook = Path(args.workbook)
    if not workbook.is_absolute():
        workbook = root / workbook

    try:
        repair(workbook)
        return 0
    except Exception as exc:
        progress("")
        progress(
            "FAST MARKET REPAIR FAILED"
        )
        progress(
            f"{type(exc).__name__}: {exc}"
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
