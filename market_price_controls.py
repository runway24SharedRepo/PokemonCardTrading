from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from market_updater.pricing import PriceVariant


XL_UP = -4162
XL_CENTER = -4108


CONTROL_HEADERS = [
    "Enabled",
    "Card ID",
    "Card Name",
    "Set Name",
    "Card Number",
    "Variant",
    "Override Market Value (£)",
    "Override Source",
    "Source URL",
    "Source Date",
    "PriceCharting Product ID",
    "Auto Update",
    "Notes",
    "Last Applied",
]


@dataclass(frozen=True)
class MarketPriceControl:
    card_id: str
    variant: str
    override_value_gbp: float
    override_source: str
    source_url: str = ""
    source_date: str = ""
    product_id: str = ""
    auto_update: bool = False
    notes: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (
            self.card_id.strip().casefold(),
            self.variant.strip().casefold(),
        )


@dataclass(frozen=True)
class EffectiveMarketValue:
    effective_value_gbp: float
    effective_source: str
    effective_source_date: str
    effective_source_url: str
    notes: str
    base_value_gbp: float
    base_source: str
    override_value_gbp: float | None
    override_source: str
    price_status: str


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _yes(value: Any) -> bool:
    return _text(value).casefold() in {
        "yes",
        "true",
        "1",
        "on",
    }


def _get_or_add_sheet(workbook, name: str):
    try:
        return workbook.Worksheets(name)
    except Exception:
        sheet = workbook.Worksheets.Add(
            After=workbook.Worksheets(
                workbook.Worksheets.Count
            )
        )
        sheet.Name = name
        return sheet


def _last_row(sheet, column: int = 1) -> int:
    try:
        return max(
            1,
            int(
                sheet.Cells(
                    sheet.Rows.Count,
                    column,
                ).End(XL_UP).Row
            ),
        )
    except Exception:
        return 1


def ensure_controls_sheet(
    workbook,
    sheet_name: str = "Market Price Controls",
) -> Any:
    sheet = _get_or_add_sheet(
        workbook,
        sheet_name,
    )

    existing_header = _text(
        sheet.Cells(4, 1).Value
    )
    if existing_header != CONTROL_HEADERS[0]:
        try:
            sheet.Cells.UnMerge()
        except Exception:
            pass
        sheet.Cells.Clear()

        sheet.Range("A1:N1").Merge()
        sheet.Cells(1, 1).Value = (
            "Market Price Controls — "
            "Verified Overrides"
        )
        sheet.Range(
            "A1:N1"
        ).Interior.Color = 0x5D3617
        sheet.Range(
            "A1:N1"
        ).Font.Color = 0xFFFFFF
        sheet.Range(
            "A1:N1"
        ).Font.Bold = True
        sheet.Range(
            "A1:N1"
        ).Font.Size = 16
        sheet.Rows(1).RowHeight = 28

        sheet.Range("A2:N2").Merge()
        sheet.Cells(2, 1).Value = (
            "Market Data Import column H is "
            "the scanner's single source of truth. "
            "Add exact card-ID + variant overrides "
            "here. PriceCharting values can be "
            "entered manually or updated through "
            "the official paid PriceCharting API."
        )
        sheet.Range(
            "A2:N2"
        ).Interior.Color = 0xF7EAD9
        sheet.Range(
            "A2:N2"
        ).WrapText = True
        sheet.Rows(2).RowHeight = 42

        sheet.Range(
            sheet.Cells(4, 1),
            sheet.Cells(
                4,
                len(CONTROL_HEADERS),
            ),
        ).Value = (
            tuple(CONTROL_HEADERS),
        )

    header = sheet.Range(
        sheet.Cells(4, 1),
        sheet.Cells(
            4,
            len(CONTROL_HEADERS),
        ),
    )
    header.Interior.Color = 0x5D3617
    header.Font.Color = 0xFFFFFF
    header.Font.Bold = True
    header.WrapText = True
    header.HorizontalAlignment = XL_CENTER
    sheet.Rows(4).RowHeight = 38

    widths = [
        10, 18, 25, 25, 12, 24, 22,
        25, 48, 14, 22, 12, 55, 20,
    ]
    for index, width in enumerate(
        widths,
        start=1,
    ):
        sheet.Columns(index).ColumnWidth = width

    sheet.Range(
        "E5:E5000"
    ).NumberFormat = "@"
    sheet.Range(
        "G5:G5000"
    ).NumberFormat = "£0.00"
    sheet.Range(
        "J5:J5000"
    ).NumberFormat = "yyyy-mm-dd"
    sheet.Range(
        "N5:N5000"
    ).NumberFormat = "yyyy-mm-dd hh:mm"

    try:
        for column, values in (
            (1, "YES,NO"),
            (8, "PriceCharting,Manual Verified,Other"),
            (12, "YES,NO"),
        ):
            target = sheet.Range(
                sheet.Cells(5, column),
                sheet.Cells(5000, column),
            )
            try:
                target.Validation.Delete()
            except Exception:
                pass
            target.Validation.Add(
                Type=3,
                AlertStyle=1,
                Operator=1,
                Formula1=values,
            )
            target.Validation.InCellDropdown = True
    except Exception:
        pass

    try:
        sheet.Tab.Color = 0x5D3617
    except Exception:
        pass

    return sheet


def read_controls(
    workbook,
    sheet_name: str = "Market Price Controls",
) -> dict[tuple[str, str], MarketPriceControl]:
    sheet = ensure_controls_sheet(
        workbook,
        sheet_name,
    )
    last = _last_row(sheet, 1)
    if last < 5:
        return {}

    raw = sheet.Range(
        f"A5:N{last}"
    ).Value
    if raw is None:
        return {}
    if not isinstance(raw, tuple):
        rows = [[raw]]
    elif raw and not isinstance(raw[0], tuple):
        rows = [list(raw)]
    else:
        rows = [list(row) for row in raw]

    output: dict[
        tuple[str, str],
        MarketPriceControl,
    ] = {}

    for row in rows:
        if len(row) < len(CONTROL_HEADERS):
            row.extend(
                [None]
                * (
                    len(CONTROL_HEADERS)
                    - len(row)
                )
            )

        if not _yes(row[0]):
            continue

        card_id = _text(row[1])
        variant = _text(row[5])
        override = _positive(row[6])
        if (
            not card_id
            or not variant
            or override is None
        ):
            continue

        control = MarketPriceControl(
            card_id=card_id,
            variant=variant,
            override_value_gbp=override,
            override_source=(
                _text(row[7])
                or "Manual Verified"
            ),
            source_url=_text(row[8]),
            source_date=_text(row[9]),
            product_id=_text(row[10]),
            auto_update=_yes(row[11]),
            notes=_text(row[12]),
        )
        output[control.key] = control

    return output


def resolve_effective_value(
    price: PriceVariant,
    controls: dict[
        tuple[str, str],
        MarketPriceControl,
    ],
) -> EffectiveMarketValue:
    base_value = float(
        price.price_gbp
    )
    base_source = str(
        price.source or ""
    )
    control = controls.get(
        (
            price.card_id.strip().casefold(),
            price.variant.strip().casefold(),
        )
    )

    if control is None:
        if "TCGplayer" in base_source:
            status = "TCGPLAYER PRIMARY"
        elif "Cardmarket" in base_source:
            status = "CARDMARKET FALLBACK"
        else:
            status = "IMPORTED SOURCE"

        return EffectiveMarketValue(
            effective_value_gbp=base_value,
            effective_source=base_source,
            effective_source_date=str(
                price.source_date or ""
            ),
            effective_source_url=str(
                price.source_url or ""
            ),
            notes=(
                f"{price.original_currency} "
                f"{price.original_price:.2f} "
                f"{price.source_field}; "
                "converted to GBP."
            ),
            base_value_gbp=base_value,
            base_source=base_source,
            override_value_gbp=None,
            override_source="",
            price_status=status,
        )

    source = (
        control.override_source
        or "Manual Verified"
    )
    status = (
        "PRICECHARTING OVERRIDE"
        if "pricecharting"
        in source.casefold()
        else "VERIFIED OVERRIDE"
    )
    note_parts = [
        (
            f"Effective value overridden from "
            f"£{base_value:.2f} "
            f"({base_source})."
        )
    ]
    if control.notes:
        note_parts.append(control.notes)

    return EffectiveMarketValue(
        effective_value_gbp=(
            control.override_value_gbp
        ),
        effective_source=source,
        effective_source_date=(
            control.source_date
        ),
        effective_source_url=(
            control.source_url
        ),
        notes=" ".join(note_parts),
        base_value_gbp=base_value,
        base_source=base_source,
        override_value_gbp=(
            control.override_value_gbp
        ),
        override_source=source,
        price_status=status,
    )


def mark_controls_applied(
    workbook,
    controls: dict[
        tuple[str, str],
        MarketPriceControl,
    ],
    sheet_name: str = "Market Price Controls",
) -> None:
    if not controls:
        return

    sheet = ensure_controls_sheet(
        workbook,
        sheet_name,
    )
    last = _last_row(sheet, 1)
    now = datetime.now()

    for row_number in range(5, last + 1):
        card_id = _text(
            sheet.Cells(
                row_number,
                2,
            ).Value
        )
        variant = _text(
            sheet.Cells(
                row_number,
                6,
            ).Value
        )
        key = (
            card_id.casefold(),
            variant.casefold(),
        )
        if key in controls:
            sheet.Cells(
                row_number,
                14,
            ).Value = now
