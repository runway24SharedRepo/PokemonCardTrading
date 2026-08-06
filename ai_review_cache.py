from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_review_models import APIUsage, ListingAIReview, ReviewExecution


class AIReviewCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS reviews(
                fingerprint TEXT PRIMARY KEY,
                stored_at TEXT NOT NULL,
                model TEXT NOT NULL,
                response_id TEXT NOT NULL,
                review_json TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                cached_input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL
            )"""
        )
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS usage_ledger(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stored_at TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                cached_input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL
            )"""
        )
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS ebay_details(
                item_id TEXT PRIMARY KEY,
                stored_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def get_review(self, fingerprint: str) -> ReviewExecution | None:
        row = self.connection.execute(
            """SELECT model,response_id,review_json,input_tokens,
                      cached_input_tokens,output_tokens,estimated_cost_usd
               FROM reviews WHERE fingerprint = ?""",
            (fingerprint,),
        ).fetchone()
        if not row:
            return None
        review = ListingAIReview.model_validate(json.loads(row[2]))
        return ReviewExecution(
            review=review,
            usage=APIUsage(
                input_tokens=int(row[3]),
                cached_input_tokens=int(row[4]),
                output_tokens=int(row[5]),
                estimated_cost_usd=float(row[6]),
            ),
            model=str(row[0]),
            cached=True,
            fingerprint=fingerprint,
            response_id=str(row[1]),
        )

    def put_review(self, execution: ReviewExecution) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """INSERT INTO reviews(
                   fingerprint,stored_at,model,response_id,review_json,
                   input_tokens,cached_input_tokens,output_tokens,estimated_cost_usd
               ) VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(fingerprint) DO UPDATE SET
                   stored_at=excluded.stored_at,model=excluded.model,
                   response_id=excluded.response_id,review_json=excluded.review_json,
                   input_tokens=excluded.input_tokens,
                   cached_input_tokens=excluded.cached_input_tokens,
                   output_tokens=excluded.output_tokens,
                   estimated_cost_usd=excluded.estimated_cost_usd""",
            (
                execution.fingerprint,
                now,
                execution.model,
                execution.response_id,
                execution.review.model_dump_json(),
                execution.usage.input_tokens,
                execution.usage.cached_input_tokens,
                execution.usage.output_tokens,
                execution.usage.estimated_cost_usd,
            ),
        )
        self.connection.execute(
            """INSERT INTO usage_ledger(
                   stored_at,fingerprint,model,input_tokens,cached_input_tokens,
                   output_tokens,estimated_cost_usd
               ) VALUES (?,?,?,?,?,?,?)""",
            (
                now,
                execution.fingerprint,
                execution.model,
                execution.usage.input_tokens,
                execution.usage.cached_input_tokens,
                execution.usage.output_tokens,
                execution.usage.estimated_cost_usd,
            ),
        )
        self.connection.commit()

    def current_month_spend(self) -> float:
        prefix = datetime.now(timezone.utc).strftime("%Y-%m")
        row = self.connection.execute(
            "SELECT COALESCE(SUM(estimated_cost_usd),0) FROM usage_ledger WHERE stored_at LIKE ?",
            (f"{prefix}%",),
        ).fetchone()
        return float(row[0] or 0)

    def get_ebay_details(self, item_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT payload_json FROM ebay_details WHERE item_id = ?", (item_id,)
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def put_ebay_details(self, item_id: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            """INSERT INTO ebay_details(item_id,stored_at,payload_json)
               VALUES (?,?,?)
               ON CONFLICT(item_id) DO UPDATE SET
                   stored_at=excluded.stored_at,payload_json=excluded.payload_json""",
            (
                item_id,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        self.connection.commit()
