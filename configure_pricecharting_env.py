from __future__ import annotations

import getpass
from pathlib import Path


def update_env(
    path: Path,
    key: str,
    value: str,
) -> None:
    lines = (
        path.read_text(
            encoding="utf-8-sig"
        ).splitlines()
        if path.exists()
        else []
    )
    prefix = f"{key}="
    output: list[str] = []
    found = False

    for line in lines:
        if line.startswith(prefix):
            output.append(
                f"{key}={value}"
            )
            found = True
        else:
            output.append(line)

    if not found:
        if output and output[-1].strip():
            output.append("")
        output.append(
            f"{key}={value}"
        )

    path.write_text(
        "\n".join(output).rstrip()
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    root = Path(__file__).resolve().parent
    token = getpass.getpass(
        "PriceCharting API token: "
    ).strip()
    if not token:
        print("No token entered.")
        return 1

    update_env(
        root / ".env",
        "PRICECHARTING_API_TOKEN",
        token,
    )
    print(
        "PriceCharting token saved to .env."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
