from __future__ import annotations

import gzip
import json
import random
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .pricing import FxRates


class PokemonTcgClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        page_size: int,
        delay_seconds: float,
        timeout_seconds: int,
        retry_attempts: int,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key.strip()
        self.page_size = page_size
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds

        # A full catalogue download is long enough that temporary 5xx
        # incidents should be tolerated more aggressively than ordinary calls.
        self.retry_attempts = max(12, int(retry_attempts))

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "PokemonAuctionScanner-MarketUpdater/1.0.1",
            }
        )
        if self.api_key:
            self.session.headers["X-Api-Key"] = self.api_key

        # The updater BAT runs from the scanner root, so this stays beside the
        # SQLite/CSV output. It is deleted after a complete successful download.
        self.checkpoint_folder = (
            Path.cwd() / "data" / "pokemon-tcg-download-checkpoint"
        )

    @staticmethod
    def _server_wait_seconds(attempt: int) -> float:
        schedule = [5, 10, 20, 30, 45, 60, 75, 90, 90, 90, 90, 90]
        base = schedule[min(attempt, len(schedule) - 1)]
        return base + random.random() * 2

    def _get(self, url: str, params: dict[str, Any]) -> requests.Response:
        last_error: Exception | None = None

        for attempt in range(self.retry_attempts):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout_seconds,
                )

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_seconds = (
                        float(retry_after)
                        if retry_after
                        else self._server_wait_seconds(attempt)
                    )
                    print(
                        f"API rate limit response; waiting "
                        f"{wait_seconds:.0f} seconds before retry "
                        f"{attempt + 2}/{self.retry_attempts}...",
                        flush=True,
                    )
                    time.sleep(wait_seconds)
                    continue

                if response.status_code in {500, 502, 503, 504}:
                    detail = response.text.strip().replace("\n", " ")[:300]
                    last_error = requests.HTTPError(
                        f"Temporary API response {response.status_code}: "
                        f"{detail or '(empty response)'}",
                        response=response,
                    )

                    if attempt + 1 >= self.retry_attempts:
                        break

                    wait_seconds = self._server_wait_seconds(attempt)
                    print(
                        f"Pokémon TCG API returned HTTP "
                        f"{response.status_code}; waiting "
                        f"{wait_seconds:.0f} seconds before retry "
                        f"{attempt + 2}/{self.retry_attempts}...",
                        flush=True,
                    )
                    time.sleep(wait_seconds)
                    continue

                response.raise_for_status()
                return response

            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 >= self.retry_attempts:
                    break

                wait_seconds = self._server_wait_seconds(attempt)
                print(
                    f"Network/API request failed; waiting "
                    f"{wait_seconds:.0f} seconds before retry "
                    f"{attempt + 2}/{self.retry_attempts}...",
                    flush=True,
                )
                time.sleep(wait_seconds)

        raise RuntimeError(
            f"Pokémon TCG API request failed after "
            f"{self.retry_attempts} attempts: {last_error}. "
            f"Downloaded pages have been saved. Run the daily BAT again "
            f"later and it will resume automatically."
        )

    def test_connection(self) -> dict[str, Any]:
        response = self._get(
            self.api_url,
            {"page": 1, "pageSize": 1, "select": "id,name,set,number"},
        )
        payload = response.json()
        return {
            "ok": True,
            "count": payload.get("count", 0),
            "total_count": payload.get("totalCount", 0),
            "api_key_used": bool(self.api_key),
        }

    def _manifest_path(self) -> Path:
        return self.checkpoint_folder / "manifest.json"

    def _page_path(self, page: int) -> Path:
        return self.checkpoint_folder / f"page-{page:05d}.json.gz"

    def _clear_checkpoint(self) -> None:
        if self.checkpoint_folder.exists():
            shutil.rmtree(self.checkpoint_folder)

    def _load_checkpoint(
        self,
    ) -> tuple[list[dict[str, Any]], int, int | None]:
        manifest_path = self._manifest_path()
        if not manifest_path.exists():
            return [], 1, None

        try:
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            if int(manifest.get("page_size", 0)) != self.page_size:
                print(
                    "Existing market-download checkpoint used a different "
                    "page size; restarting the catalogue download.",
                    flush=True,
                )
                self._clear_checkpoint()
                return [], 1, None

            next_page = int(manifest.get("next_page", 1))
            total_count = manifest.get("total_count")
            cards: list[dict[str, Any]] = []

            for page in range(1, next_page):
                page_path = self._page_path(page)
                if not page_path.exists():
                    raise FileNotFoundError(
                        f"Checkpoint page is missing: {page_path}"
                    )
                with gzip.open(page_path, "rt", encoding="utf-8") as handle:
                    page_payload = json.load(handle)
                cards.extend(page_payload.get("data") or [])

            print(
                f"Resuming incomplete download at page {next_page}. "
                f"Recovered {len(cards)} previously downloaded cards.",
                flush=True,
            )
            return cards, next_page, (
                int(total_count) if total_count is not None else None
            )
        except Exception as exc:
            print(
                f"Checkpoint could not be read ({exc}); restarting the "
                f"catalogue download.",
                flush=True,
            )
            self._clear_checkpoint()
            return [], 1, None

    def _save_page_checkpoint(
        self,
        page: int,
        page_cards: list[dict[str, Any]],
        total_count: int,
    ) -> None:
        self.checkpoint_folder.mkdir(parents=True, exist_ok=True)

        page_path = self._page_path(page)
        temp_page = page_path.with_suffix(page_path.suffix + ".tmp")
        with gzip.open(temp_page, "wt", encoding="utf-8") as handle:
            json.dump(
                {"page": page, "data": page_cards},
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        temp_page.replace(page_path)

        manifest = {
            "version": 1,
            "page_size": self.page_size,
            "next_page": page + 1,
            "total_count": total_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = self._manifest_path()
        temp_manifest = manifest_path.with_suffix(".json.tmp")
        temp_manifest.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        temp_manifest.replace(manifest_path)

    def fetch_all_cards(
        self,
        progress,
        maximum_pages: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        use_checkpoint = maximum_pages is None

        if use_checkpoint:
            cards, page, total_count = self._load_checkpoint()
        else:
            cards, page, total_count = [], 1, None

        pages_downloaded_this_run = 0

        while True:
            if pages_downloaded_this_run > 0:
                time.sleep(self.delay_seconds)

            response = self._get(
                self.api_url,
                {
                    "page": page,
                    "pageSize": self.page_size,
                    "orderBy": "set.releaseDate,number",
                },
            )
            payload = response.json()
            page_cards = payload.get("data") or []
            total_count = int(payload.get("totalCount") or total_count or 0)

            # Persist the page before moving on, so even a power loss or later
            # API outage cannot discard it.
            if use_checkpoint and page_cards:
                self._save_page_checkpoint(
                    page=page,
                    page_cards=page_cards,
                    total_count=total_count,
                )

            cards.extend(page_cards)
            pages_downloaded_this_run += 1

            progress(
                page=page,
                received=len(page_cards),
                accumulated=len(cards),
                total_count=total_count,
            )

            if not page_cards:
                break
            if len(cards) >= total_count:
                break
            if maximum_pages is not None and page >= maximum_pages:
                break

            page += 1

        metadata = {
            "pages": page,
            "cards_downloaded": len(cards),
            "total_count": total_count or len(cards),
            "resumable_checkpoint": use_checkpoint,
        }

        # A complete successful fetch no longer needs its temporary pages.
        if use_checkpoint and len(cards) >= (total_count or len(cards)):
            self._clear_checkpoint()

        return cards, metadata


def fetch_fx_rates(
    session: requests.Session,
    api_url: str,
    timeout_seconds: int,
    eur_override: str,
    usd_override: str,
    previous_rates: FxRates | None,
) -> FxRates:
    if eur_override.strip() and usd_override.strip():
        return FxRates(
            eur_to_gbp=float(eur_override),
            usd_to_gbp=float(usd_override),
            source="Manual .env overrides",
            rate_date=time.strftime("%Y-%m-%d"),
        )

    try:
        response = session.get(api_url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        rates = payload["rates"]
        eur_to_gbp = float(rates["GBP"])
        eur_to_usd = float(rates["USD"])
        usd_to_gbp = eur_to_gbp / eur_to_usd
        return FxRates(
            eur_to_gbp=eur_to_gbp,
            usd_to_gbp=usd_to_gbp,
            source="Frankfurter reference rates",
            rate_date=str(payload.get("date", time.strftime("%Y-%m-%d"))),
        )
    except Exception:
        if previous_rates is not None:
            return previous_rates
        raise


def save_gzip_snapshot(
    cards: list[dict[str, Any]],
    path: Path,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": metadata,
        "data": cards,
    }
    temp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temp, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    temp.replace(path)
