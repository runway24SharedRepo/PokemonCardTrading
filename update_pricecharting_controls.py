from __future__ import annotations

import os
import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from market_price_controls import (
    ensure_controls_sheet,
)


def text(value: Any) -> str:
    return str(value or "").strip()


def normalise(value: Any) -> str:
    raw = unicodedata.normalize(
        "NFKD",
        text(value),
    )
    raw = "".join(
        character
        for character in raw
        if not unicodedata.combining(
            character
        )
    ).casefold()
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        raw,
    ).strip()


def yes(value: Any) -> bool:
    return normalise(value) in {
        "yes",
        "true",
        "1",
        "on",
    }


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


def usd_to_gbp(workbook) -> float:
    summary = workbook.Worksheets(
        "Market Update Summary"
    )
    for row_number in range(4, 31):
        label = normalise(
            summary.Cells(
                row_number,
                1,
            ).Value
        )
        value = positive(
            summary.Cells(
                row_number,
                2,
            ).Value
        )
        if (
            value is not None
            and "usd" in label
            and "gbp" in label
        ):
            return value
    raise RuntimeError(
        "USD to GBP rate was not found "
        "in Market Update Summary."
    )


def variant_markers(variant: str) -> dict[str, bool]:
    value = normalise(variant)
    return {
        "first": (
            "1st edition" in value
            or "first edition" in value
        ),
        "shadowless": (
            "shadowless" in value
        ),
        "reverse": (
            "reverse" in value
        ),
    }


def product_score(
    product: dict[str, Any],
    card_name: str,
    set_name: str,
    number: str,
    variant: str,
) -> float:
    product_name = normalise(
        product.get(
            "product-name",
            "",
        )
    )
    console_name = normalise(
        product.get(
            "console-name",
            "",
        )
    )
    expected_name = normalise(card_name)
    expected_set = normalise(set_name)
    expected_number = re.sub(
        r"[^a-z0-9]+",
        "",
        normalise(number),
    )

    score = 0.0
    if expected_name and expected_name in product_name:
        score += 0.45
    if (
        expected_number
        and re.search(
            rf"(?<![a-z0-9])0*"
            rf"{re.escape(expected_number)}"
            rf"(?![a-z0-9])",
            product_name,
        )
    ):
        score += 0.30

    set_tokens = {
        token
        for token in expected_set.split()
        if len(token) >= 3
    }
    if set_tokens:
        score += (
            0.20
            * len(
                set_tokens
                & set(
                    console_name.split()
                )
            )
            / len(set_tokens)
        )

    expected = variant_markers(variant)
    product_first = (
        "1st edition" in product_name
        or "first edition"
        in product_name
    )
    product_shadowless = (
        "shadowless" in product_name
    )
    product_reverse = (
        "reverse" in product_name
    )

    for key, observed in (
        ("first", product_first),
        ("shadowless", product_shadowless),
        ("reverse", product_reverse),
    ):
        if expected[key] == observed:
            score += 0.05
        elif expected[key] or observed:
            score -= 0.40

    return score


def get_json(
    session: requests.Session,
    path: str,
    token: str,
    **params: Any,
) -> dict[str, Any]:
    response = session.get(
        (
            "https://www.pricecharting.com"
            + path
        ),
        params={
            "t": token,
            **params,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success":
        raise RuntimeError(
            payload.get(
                "error-message",
                "PriceCharting API error",
            )
        )
    return payload


def update(workbook_path: Path) -> int:
    load_dotenv(
        workbook_path.parent / ".env",
        override=True,
        encoding="utf-8-sig",
    )
    token = os.getenv(
        "PRICECHARTING_API_TOKEN",
        "",
    ).strip()
    if not token:
        raise RuntimeError(
            "PRICECHARTING_API_TOKEN is missing. "
            "Official API access requires a "
            "PriceCharting Legendary subscription."
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

    updated = 0
    skipped = 0
    errors = 0
    session = requests.Session()

    try:
        sheet = ensure_controls_sheet(
            book
        )
        rate = usd_to_gbp(book)
        end = last_row(sheet, 1)

        for row_number in range(
            5,
            end + 1,
        ):
            if not yes(
                sheet.Cells(
                    row_number,
                    1,
                ).Value
            ):
                continue
            if not yes(
                sheet.Cells(
                    row_number,
                    12,
                ).Value
            ):
                continue

            card_id = text(
                sheet.Cells(
                    row_number,
                    2,
                ).Value
            )
            card_name = text(
                sheet.Cells(
                    row_number,
                    3,
                ).Value
            )
            set_name = text(
                sheet.Cells(
                    row_number,
                    4,
                ).Value
            )
            number = text(
                sheet.Cells(
                    row_number,
                    5,
                ).Value
            )
            variant = text(
                sheet.Cells(
                    row_number,
                    6,
                ).Value
            )
            product_id = text(
                sheet.Cells(
                    row_number,
                    11,
                ).Value
            )

            if (
                not card_id
                or not card_name
                or not set_name
                or not number
                or not variant
            ):
                skipped += 1
                continue

            try:
                if not product_id:
                    query = (
                        f"{card_name} #{number} "
                        f"Pokemon {set_name}"
                    )
                    search = get_json(
                        session,
                        "/api/products",
                        token,
                        q=query,
                    )
                    products = (
                        search.get("products")
                        or []
                    )
                    ranked = sorted(
                        (
                            (
                                product_score(
                                    product,
                                    card_name,
                                    set_name,
                                    number,
                                    variant,
                                ),
                                product,
                            )
                            for product in products
                        ),
                        key=lambda item: item[0],
                        reverse=True,
                    )
                    if (
                        not ranked
                        or ranked[0][0] < 0.75
                        or (
                            len(ranked) > 1
                            and ranked[0][0]
                            - ranked[1][0]
                            < 0.08
                        )
                    ):
                        sheet.Cells(
                            row_number,
                            13,
                        ).Value = (
                            "PriceCharting match "
                            "ambiguous; enter Product "
                            "ID manually."
                        )
                        errors += 1
                        time.sleep(1.05)
                        continue

                    product_id = text(
                        ranked[0][1].get(
                            "id",
                            "",
                        )
                    )
                    sheet.Cells(
                        row_number,
                        11,
                    ).Value = product_id
                    time.sleep(1.05)

                product = get_json(
                    session,
                    "/api/product",
                    token,
                    id=product_id,
                )
                pennies = positive(
                    product.get(
                        "loose-price"
                    )
                )
                if pennies is None:
                    raise RuntimeError(
                        "No ungraded/loose price "
                        "was returned."
                    )

                usd_value = pennies / 100
                gbp_value = round(
                    usd_value * rate,
                    2,
                )

                sheet.Cells(
                    row_number,
                    7,
                ).Value = gbp_value
                sheet.Cells(
                    row_number,
                    8,
                ).Value = "PriceCharting"
                sheet.Cells(
                    row_number,
                    9,
                ).Value = (
                    "https://www.pricecharting.com/"
                    "search-products?q="
                    + requests.utils.quote(
                        f"{card_name} {number}"
                    )
                )
                sheet.Cells(
                    row_number,
                    10,
                ).Value = date.today()
                sheet.Cells(
                    row_number,
                    13,
                ).Value = (
                    f"Official API loose-price "
                    f"USD {usd_value:.2f}; "
                    f"converted at USD→GBP "
                    f"{rate:.6f}."
                )
                sheet.Cells(
                    row_number,
                    14,
                ).Value = datetime.now()
                updated += 1

                print(
                    f"{card_name} {number} "
                    f"{variant}: £{gbp_value:.2f}"
                )
                time.sleep(1.05)

            except Exception as exc:
                sheet.Cells(
                    row_number,
                    13,
                ).Value = (
                    f"PriceCharting error: "
                    f"{str(exc)[:300]}"
                )
                errors += 1
                time.sleep(1.05)

        book.Save()

        print()
        print(
            "PRICECHARTING CONTROL UPDATE "
            "COMPLETE"
        )
        print(f"Updated: {updated}")
        print(f"Skipped: {skipped}")
        print(f"Errors: {errors}")
        print(
            "Run applyMarketPriceControls.bat "
            "to apply these values to "
            "Market Data Import."
        )
        return 0

    finally:
        try:
            book.Close(
                SaveChanges=True
            )
        finally:
            excel.Quit()


def main() -> int:
    root = Path(__file__).resolve().parent
    workbook = root / (
        "Pokemon-Auction-Scanner-"
        "Dashboard.xlsx"
    )
    return update(workbook)


if __name__ == "__main__":
    raise SystemExit(main())
