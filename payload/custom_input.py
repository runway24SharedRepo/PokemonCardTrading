from __future__ import annotations

import re


def parse_market_data_references(text: str) -> list[tuple[str, int]]:
    """Parse unique Market Data Import column-H references in file order."""

    references: list[tuple[str, int]] = []
    seen: set[int] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        value = raw_line.lstrip("\ufeff").split("#", 1)[0].strip()
        if not value:
            continue
        match = re.fullmatch(r"\$?H\$?(\d+)", value, flags=re.IGNORECASE)
        if not match:
            raise ValueError(
                f"pokemonInput.txt line {line_number}: '{value}' is invalid. "
                "Use one column-H reference per line, for example H1811."
            )
        row_number = int(match.group(1))
        if row_number < 5:
            raise ValueError(
                f"pokemonInput.txt line {line_number}: H{row_number} is a "
                "header row, not a Market Data Import card row."
            )
        if row_number in seen:
            continue
        seen.add(row_number)
        references.append((f"H{row_number}", row_number))

    if not references:
        raise ValueError(
            "pokemonInput.txt contains no column-H card references."
        )
    return references
