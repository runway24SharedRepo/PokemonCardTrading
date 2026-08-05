from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def seller_key(seller: str) -> str:
    return str(seller or "").strip().casefold()


class SellerRadarHistory:
    """Persistent per-seller record of eBay listings already analysed."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {
            "version": 1,
            "sellers": {},
        }
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            loaded = json.loads(
                self.path.read_text(encoding="utf-8")
            )
            if isinstance(loaded, dict):
                self.data = loaded
                self.data.setdefault("version", 1)
                self.data.setdefault("sellers", {})
        except (OSError, json.JSONDecodeError):
            corrupt = self.path.with_suffix(
                self.path.suffix + ".corrupt"
            )
            try:
                self.path.replace(corrupt)
            except OSError:
                pass
            self.data = {
                "version": 1,
                "sellers": {},
            }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )
        temporary.write_text(
            json.dumps(
                self.data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def _record(
        self,
        seller: str,
        *,
        create: bool,
    ) -> dict[str, Any] | None:
        key = seller_key(seller)
        sellers = self.data.setdefault("sellers", {})
        record = sellers.get(key)

        if record is None and create:
            record = {
                "seller": str(seller or "").strip(),
                "created_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "updated_at": "",
                "items": {},
                "runs": [],
            }
            sellers[key] = record

        if record is not None:
            record.setdefault(
                "seller",
                str(seller or "").strip(),
            )
            record.setdefault("items", {})
            record.setdefault("runs", [])
        return record

    def seen_item_ids(self, seller: str) -> set[str]:
        record = self._record(seller, create=False)
        if not record:
            return set()
        return {
            str(item_id)
            for item_id in record.get("items", {})
            if str(item_id).strip()
        }

    def scanned_count(self, seller: str) -> int:
        return len(self.seen_item_ids(seller))

    def completed_run_count(self, seller: str) -> int:
        record = self._record(seller, create=False)
        return len(record.get("runs", [])) if record else 0

    def record_batch(
        self,
        seller: str,
        items: Iterable[dict[str, Any]],
        outcomes: dict[str, dict[str, Any]],
        run_summary: dict[str, Any],
    ) -> int:
        record = self._record(seller, create=True)
        assert record is not None

        now = datetime.now(timezone.utc).isoformat()
        run_id = str(
            run_summary.get("run_id", "") or ""
        )
        added = 0

        item_store = record.setdefault("items", {})
        for item in items:
            item_id = str(
                item.get("itemId", "") or ""
            ).strip()
            if not item_id:
                continue

            previous = item_store.get(item_id, {})
            outcome = outcomes.get(item_id, {})
            if item_id not in item_store:
                added += 1

            item_store[item_id] = {
                "item_id": item_id,
                "title": str(
                    item.get("title", "") or ""
                ),
                "first_scanned_at": previous.get(
                    "first_scanned_at",
                    now,
                ),
                "last_scanned_at": now,
                "run_id": run_id,
                "matched": bool(
                    outcome.get("matched", False)
                ),
                "decision": str(
                    outcome.get("decision", "") or ""
                ),
                "reason": str(
                    outcome.get("reason", "") or ""
                ),
                "listing_type": str(
                    outcome.get("listing_type", "") or ""
                ),
            }

        run_entry = dict(run_summary)
        run_entry["recorded_at"] = now
        run_entry["new_item_ids_recorded"] = added
        record.setdefault("runs", []).append(run_entry)

        # Keep a useful audit trail without allowing the file to grow
        # indefinitely from thousands of repeated runs.
        record["runs"] = record["runs"][-250:]
        record["updated_at"] = now
        record["seller"] = str(seller or "").strip()
        return added

    def reset_seller(
        self,
        seller: str,
        *,
        backup: bool = True,
    ) -> int:
        key = seller_key(seller)
        sellers = self.data.setdefault("sellers", {})
        record = sellers.get(key)
        if not record:
            return 0

        count = len(record.get("items", {}))
        if backup and self.path.exists():
            stamp = datetime.now().strftime(
                "%Y%m%d-%H%M%S"
            )
            backup_path = self.path.with_name(
                f"{self.path.stem}-before-reset-{stamp}"
                f"{self.path.suffix}"
            )
            shutil.copy2(self.path, backup_path)

        del sellers[key]
        return count
