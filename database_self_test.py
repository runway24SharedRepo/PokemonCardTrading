from pathlib import Path
import tempfile

from app.history import HistoryStore


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "scanner-self-test.sqlite"
        history = HistoryStore(str(db_path))
        try:
            assert history.performance() == []
            assert db_path.exists()
            print("SQLite history database self-test: PASS")
        finally:
            history.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
