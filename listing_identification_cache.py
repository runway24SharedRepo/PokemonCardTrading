from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


MATCHER_VERSION = "phase5.6.3.2-exact-identity-v1"


class ListingIdentificationCache:
    """Durable exact-title matching results keyed by eBay item ID.

    Every completed match is committed independently. SQLite WAL recovery means
    closing the BAT cannot discard earlier completed identifications; at worst,
    the title being evaluated at the instant of termination is repeated.
    """

    def __init__(self, root: Path, candidates: Iterable[Any]) -> None:
        path = Path(root) / "data" / "listing-identification-cache.sqlite"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        # WAL + NORMAL keeps each autocommitted result durable across a BAT
        # termination without forcing a slow full disk sync for every title.
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS listing_identifications (
              item_id TEXT PRIMARY KEY,
              title_hash TEXT NOT NULL,
              title TEXT NOT NULL,
              matcher_version TEXT NOT NULL,
              candidate_identity TEXT NOT NULL,
              match_score REAL NOT NULL,
              reason TEXT NOT NULL,
              stored_at TEXT NOT NULL
            )
            """
        )
        self.candidates = {
            str(candidate.identity): candidate for candidate in candidates
        }
        self.hits = 0
        self.misses = 0
        self.writes = 0

    @staticmethod
    def _title_hash(title: str) -> str:
        return hashlib.sha256(title.encode("utf-8")).hexdigest()

    def lookup(
        self, item_id: str, title: str
    ) -> tuple[bool, Any | None, float, str]:
        row = self.db.execute(
            """
            SELECT title_hash, matcher_version, candidate_identity,
                   match_score, reason
            FROM listing_identifications WHERE item_id = ?
            """,
            (item_id,),
        ).fetchone()
        if (
            row is None
            or row[0] != self._title_hash(title)
            or row[1] != MATCHER_VERSION
        ):
            self.misses += 1
            return False, None, 0.0, ""

        identity = str(row[2] or "")
        if identity:
            candidate = self.candidates.get(identity)
            if candidate is None:
                # The catalogue changed. Recalculate this entry against the
                # current database rather than returning a stale identity.
                self.misses += 1
                return False, None, 0.0, ""
        else:
            candidate = None

        self.hits += 1
        return True, candidate, float(row[3]), str(row[4] or "")

    def store(
        self,
        item_id: str,
        title: str,
        candidate: Any | None,
        score: float,
        reason: str,
    ) -> None:
        identity = str(candidate.identity) if candidate is not None else ""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.db.execute(
            """
            INSERT INTO listing_identifications
              (item_id, title_hash, title, matcher_version,
               candidate_identity, match_score, reason, stored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
              title_hash=excluded.title_hash,
              title=excluded.title,
              matcher_version=excluded.matcher_version,
              candidate_identity=excluded.candidate_identity,
              match_score=excluded.match_score,
              reason=excluded.reason,
              stored_at=excluded.stored_at
            """,
            (
                item_id,
                self._title_hash(title),
                title,
                MATCHER_VERSION,
                identity,
                float(score),
                str(reason or ""),
                now,
            ),
        )
        self.writes += 1

    def match(self, matcher: Any, item: dict[str, Any], exclusions: Iterable[str]):
        item_id = str(item.get("itemId", "") or "")
        title = str(item.get("title", "") or "")
        found, candidate, score, reason = self.lookup(item_id, title)
        if found:
            return candidate, score, reason, True

        candidate, score, reason = matcher.match(title, exclusions)
        if item_id:
            self.store(item_id, title, candidate, score, reason)
        return candidate, score, reason, False

    def total_rows(self) -> int:
        return int(
            self.db.execute(
                "SELECT COUNT(*) FROM listing_identifications"
            ).fetchone()[0]
        )

    def close(self) -> None:
        self.db.close()
