import tempfile
import unittest
from pathlib import Path

from app.history import HistoryStore


class HistoryTests(unittest.TestCase):
    def test_empty_performance(self):
        # NamedTemporaryFile remains locked on Windows and SQLite cannot
        # reopen it. A TemporaryDirectory gives SQLite a normal unlocked path.
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "scanner-history-test.sqlite"
            history = HistoryStore(str(db_path))
            try:
                self.assertEqual(history.performance(), [])
                self.assertTrue(db_path.exists())
            finally:
                history.close()


if __name__ == "__main__":
    unittest.main()
