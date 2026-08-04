from __future__ import annotations

from pathlib import Path


SETTINGS = [
    ("EBAY_WATCHLIST_ENABLED", "YES"),
    ("EBAY_USER_REFRESH_TOKEN", ""),
    ("EBAY_USER_ACCESS_TOKEN", ""),
    ("EBAY_AUTH_TOKEN", ""),
    ("EBAY_USER_SCOPE", "https://api.ebay.com/oauth/api_scope"),
    ("EBAY_TRADING_SITE_ID", "3"),
    ("EBAY_TRADING_COMPATIBILITY_LEVEL", "1455"),
    ("EBAY_WATCHLIST_MAX_ADD_PER_RUN", "50"),
    ("EBAY_WATCHLIST_RECHECK_HOURS", "6"),
    ("EBAY_WATCHLIST_BATCH_SIZE", "25"),
    ("EBAY_WATCHLIST_TIMEOUT_SECONDS", "30"),
]


def existing_keys(lines: list[str]) -> set[str]:
    output: set[str] = set()
    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        output.add(clean.split("=", 1)[0].strip())
    return output


def main() -> int:
    root = Path(__file__).resolve().parent
    env_path = root / ".env"
    lines = (
        env_path.read_text(encoding="utf-8-sig").splitlines()
        if env_path.exists()
        else []
    )
    keys = existing_keys(lines)

    additions = []
    for key, value in SETTINGS:
        if key not in keys:
            additions.append(f"{key}={value}")

    if additions:
        with env_path.open("a", encoding="utf-8") as handle:
            if lines and lines[-1].strip():
                handle.write("\n")
            handle.write(
                "\n# eBay personal Watchlist integration\n"
                "# Keep user tokens private. Do not upload or share this file.\n"
            )
            for line in additions:
                handle.write(line + "\n")
        print(
            f"Added {len(additions)} Watchlist setting(s) to .env."
        )
    else:
        print("The Watchlist settings already exist in .env.")

    print()
    print("Configure ONE user-authorisation method:")
    print()
    print("Preferred long-term:")
    print("  EBAY_USER_REFRESH_TOKEN=<your production OAuth refresh token>")
    print()
    print("Temporary OAuth test:")
    print("  EBAY_USER_ACCESS_TOKEN=<your production OAuth user token>")
    print()
    print("Traditional API alternative:")
    print("  EBAY_AUTH_TOKEN=<your production Auth'n'Auth user token>")
    print()
    print("Never share the .env file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
