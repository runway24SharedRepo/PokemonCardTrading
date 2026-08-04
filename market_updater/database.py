from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pricing import FxRates, PriceVariant


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS cards (
    card_id TEXT PRIMARY KEY,
    card_name TEXT NOT NULL,
    set_id TEXT,
    set_name TEXT,
    card_number TEXT,
    rarity TEXT,
    supertype TEXT,
    subtypes TEXT,
    types TEXT,
    hp TEXT,
    artist TEXT,
    release_date TEXT,
    regulation_mark TEXT,
    image_url TEXT,
    card_json TEXT NOT NULL,
    last_synced TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS current_prices (
    card_id TEXT NOT NULL,
    variant TEXT NOT NULL,
    card_name TEXT NOT NULL,
    set_id TEXT,
    set_name TEXT,
    card_number TEXT,
    price_gbp REAL NOT NULL,
    source TEXT NOT NULL,
    source_date TEXT,
    source_url TEXT,
    original_price REAL,
    original_currency TEXT,
    source_field TEXT,
    last_synced TEXT NOT NULL,
    PRIMARY KEY(card_id, variant)
);

CREATE TABLE IF NOT EXISTS price_history (
    card_id TEXT NOT NULL,
    variant TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    price_gbp REAL NOT NULL,
    source TEXT NOT NULL,
    source_date TEXT,
    PRIMARY KEY(card_id, variant, observed_at)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    rate_date TEXT PRIMARY KEY,
    eur_to_gbp REAL NOT NULL,
    usd_to_gbp REAL NOT NULL,
    source TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    cards_downloaded INTEGER DEFAULT 0,
    priced_variants INTEGER DEFAULT 0,
    changed_prices INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    message TEXT
);
"""


class MarketDatabase:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def previous_fx_rates(self) -> FxRates | None:
        row = self.connection.execute(
            """
            SELECT rate_date, eur_to_gbp, usd_to_gbp, source
            FROM fx_rates
            ORDER BY observed_at DESC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None
        return FxRates(
            eur_to_gbp=float(row["eur_to_gbp"]),
            usd_to_gbp=float(row["usd_to_gbp"]),
            source=f"{row['source']} (cached)",
            rate_date=str(row["rate_date"]),
        )

    def current_price_map(self) -> dict[tuple[str, str], float]:
        rows = self.connection.execute(
            "SELECT card_id, variant, price_gbp FROM current_prices"
        ).fetchall()
        return {
            (str(row["card_id"]), str(row["variant"])): float(row["price_gbp"])
            for row in rows
        }

    def start_run(self) -> int:
        started_at = datetime.now(timezone.utc).isoformat()
        cursor = self.connection.execute(
            """
            INSERT INTO sync_runs(started_at, status, message)
            VALUES (?, 'RUNNING', '')
            """,
            (started_at,),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def fail_run(self, run_id: int, message: str) -> None:
        self.connection.execute(
            """
            UPDATE sync_runs
            SET finished_at = ?, status = 'FAILED', message = ?
            WHERE run_id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), message[:1000], run_id),
        )
        self.connection.commit()

    def commit_sync(
        self,
        run_id: int,
        cards: list[dict[str, Any]],
        prices: list[PriceVariant],
        fx: FxRates,
        changed_prices: list[dict[str, Any]],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()

        with self.connection:
            for card in cards:
                set_info = card.get("set") or {}
                images = card.get("images") or {}
                self.connection.execute(
                    """
                    INSERT INTO cards(
                        card_id, card_name, set_id, set_name, card_number,
                        rarity, supertype, subtypes, types, hp, artist,
                        release_date, regulation_mark, image_url,
                        card_json, last_synced
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(card_id) DO UPDATE SET
                        card_name = excluded.card_name,
                        set_id = excluded.set_id,
                        set_name = excluded.set_name,
                        card_number = excluded.card_number,
                        rarity = excluded.rarity,
                        supertype = excluded.supertype,
                        subtypes = excluded.subtypes,
                        types = excluded.types,
                        hp = excluded.hp,
                        artist = excluded.artist,
                        release_date = excluded.release_date,
                        regulation_mark = excluded.regulation_mark,
                        image_url = excluded.image_url,
                        card_json = excluded.card_json,
                        last_synced = excluded.last_synced
                    """,
                    (
                        str(card.get("id", "")),
                        str(card.get("name", "")),
                        str(set_info.get("id", "")),
                        str(set_info.get("name", "")),
                        str(card.get("number", "")),
                        str(card.get("rarity", "")),
                        str(card.get("supertype", "")),
                        " | ".join(card.get("subtypes") or []),
                        " | ".join(card.get("types") or []),
                        str(card.get("hp", "")),
                        str(card.get("artist", "")),
                        str(set_info.get("releaseDate", "")),
                        str(card.get("regulationMark", "")),
                        str(images.get("large", "")),
                        json.dumps(card, ensure_ascii=False, separators=(",", ":")),
                        now,
                    ),
                )

            self.connection.execute("DELETE FROM current_prices")

            for price in prices:
                self.connection.execute(
                    """
                    INSERT INTO current_prices(
                        card_id, variant, card_name, set_id, set_name,
                        card_number, price_gbp, source, source_date,
                        source_url, original_price, original_currency,
                        source_field, last_synced
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        price.card_id,
                        price.variant,
                        price.card_name,
                        price.set_id,
                        price.set_name,
                        price.card_number,
                        price.price_gbp,
                        price.source,
                        price.source_date,
                        price.source_url,
                        price.original_price,
                        price.original_currency,
                        price.source_field,
                        now,
                    ),
                )

            for change in changed_prices:
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO price_history(
                        card_id, variant, observed_at, price_gbp,
                        source, source_date
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        change["card_id"],
                        change["variant"],
                        now,
                        change["current_price_gbp"],
                        change["source"],
                        change["source_date"],
                    ),
                )

            self.connection.execute(
                """
                INSERT INTO fx_rates(
                    rate_date, eur_to_gbp, usd_to_gbp, source, observed_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(rate_date) DO UPDATE SET
                    eur_to_gbp = excluded.eur_to_gbp,
                    usd_to_gbp = excluded.usd_to_gbp,
                    source = excluded.source,
                    observed_at = excluded.observed_at
                """,
                (
                    fx.rate_date,
                    fx.eur_to_gbp,
                    fx.usd_to_gbp,
                    fx.source,
                    now,
                ),
            )

            self.connection.execute(
                """
                UPDATE sync_runs
                SET finished_at = ?,
                    cards_downloaded = ?,
                    priced_variants = ?,
                    changed_prices = ?,
                    status = 'SUCCESS',
                    message = ?
                WHERE run_id = ?
                """,
                (
                    now,
                    len(cards),
                    len(prices),
                    len(changed_prices),
                    "Daily market update completed.",
                    run_id,
                ),
            )
