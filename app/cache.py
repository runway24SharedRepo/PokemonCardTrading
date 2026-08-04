from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from typing import Any

class SearchCache:
    def __init__(self, path: str, ttl_minutes: int = 45) -> None:
        self.path = Path(path)
        self.ttl = ttl_minutes * 60
        self.db = sqlite3.connect(self.path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS cache (
            cache_key TEXT PRIMARY KEY, created REAL NOT NULL, payload TEXT NOT NULL
        )""")
        self.db.commit()

    def get(self, key: str) -> list[dict[str, Any]] | None:
        row = self.db.execute("SELECT created,payload FROM cache WHERE cache_key=?", (key,)).fetchone()
        if not row or time.time() - row[0] > self.ttl:
            return None
        return json.loads(row[1])

    def put(self, key: str, payload: list[dict[str, Any]]) -> None:
        self.db.execute("REPLACE INTO cache(cache_key,created,payload) VALUES(?,?,?)",
                        (key, time.time(), json.dumps(payload)))
        self.db.commit()

    def close(self) -> None:
        self.db.close()
