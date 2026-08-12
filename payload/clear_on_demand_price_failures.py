from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def clear_failure_checkpoints(root: Path) -> int:
    database = Path(root) / "data" / "on-demand-price-cache.sqlite"
    if not database.exists():
        return 0
    connection = sqlite3.connect(str(database), timeout=30)
    try:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fetch_failure'"
        ).fetchone()
        if table is None:
            return 0
        count = int(connection.execute("SELECT COUNT(*) FROM fetch_failure").fetchone()[0])
        connection.execute("DELETE FROM fetch_failure")
        connection.commit()
        return count
    finally:
        connection.close()


if __name__ == "__main__":
    project_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    cleared = clear_failure_checkpoints(project_root)
    print(
        f"Cleared {cleared} old failed-price checkpoint(s); "
        "successful 24-hour prices were preserved."
    )
