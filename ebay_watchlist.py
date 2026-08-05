from __future__ import annotations

import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape

import requests
from requests.auth import HTTPBasicAuth


TRADING_ENDPOINT = "https://api.ebay.com/ws/api.dll"
OAUTH_TOKEN_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"
XML_NAMESPACE = "urn:ebay:apis:eBLBaseComponents"
DEFAULT_SCOPE = "https://api.ebay.com/oauth/api_scope"


@dataclass
class WatchlistCallResult:
    acknowledgement: str
    watchlist_count: int | None = None
    watchlist_maximum: int | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class WatchlistSyncSummary:
    enabled: bool = True
    configured: bool = True
    green_candidates: int = 0
    requested: int = 0
    confirmed: int = 0
    already_recent: int = 0
    skipped_variations: int = 0
    skipped_expired: int = 0
    failed: int = 0
    watchlist_count: int | None = None
    watchlist_maximum: int | None = None
    message: str = ""

    @property
    def display(self) -> str:
        if not self.enabled:
            return "disabled"
        if not self.configured:
            return "user token not configured"
        details = (
            f"{self.confirmed} confirmed, "
            f"{self.already_recent} already managed, "
            f"{self.failed} failed"
        )
        if self.watchlist_count is not None:
            details += f"; eBay Watchlist {self.watchlist_count}"
            if self.watchlist_maximum is not None:
                details += f"/{self.watchlist_maximum}"
        return details


@dataclass(frozen=True)
class ParsedItemId:
    browse_item_id: str
    legacy_item_id: str
    variation_id: str = "0"

    @property
    def is_multi_variation(self) -> bool:
        return self.variation_id not in {"", "0"}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return str(value).strip().upper() in {
        "1",
        "YES",
        "TRUE",
        "ON",
        "Y",
    }


def parse_item_id(value: Any) -> ParsedItemId | None:
    text = str(value or "").strip()
    if not text:
        return None

    if text.startswith("v1|"):
        parts = text.split("|")
        if len(parts) >= 3 and parts[1].isdigit():
            return ParsedItemId(
                browse_item_id=text,
                legacy_item_id=parts[1],
                variation_id=parts[2] or "0",
            )
        return None

    if text.isdigit():
        return ParsedItemId(
            browse_item_id=text,
            legacy_item_id=text,
            variation_id="0",
        )

    match = re_search_numeric_id(text)
    if match:
        return ParsedItemId(
            browse_item_id=text,
            legacy_item_id=match,
            variation_id="0",
        )
    return None


def re_search_numeric_id(value: str) -> str:
    import re

    match = re.search(r"(?<!\d)(\d{9,15})(?!\d)", value)
    return match.group(1) if match else ""


def _xml_text(
    root: ET.Element,
    name: str,
) -> str:
    element = root.find(f".//{{{XML_NAMESPACE}}}{name}")
    return str(element.text or "").strip() if element is not None else ""


def _xml_int(
    root: ET.Element,
    name: str,
) -> int | None:
    text = _xml_text(root, name)
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _response_errors(root: ET.Element) -> list[str]:
    output: list[str] = []
    for error in root.findall(
        f".//{{{XML_NAMESPACE}}}Errors"
    ):
        severity = _xml_child_text(error, "SeverityCode")
        code = _xml_child_text(error, "ErrorCode")
        short = _xml_child_text(error, "ShortMessage")
        long_message = _xml_child_text(error, "LongMessage")
        parts = [
            part
            for part in (
                severity,
                f"code {code}" if code else "",
                short,
                long_message if long_message != short else "",
            )
            if part
        ]
        output.append(" | ".join(parts))
    return output


def _xml_child_text(
    parent: ET.Element,
    name: str,
) -> str:
    child = parent.find(f"{{{XML_NAMESPACE}}}{name}")
    return str(child.text or "").strip() if child is not None else ""


class EbayWatchlistClient:
    """User-authorised eBay Trading API client for My eBay Watchlist."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv(
            "EBAY_CLIENT_SECRET",
            "",
        ).strip()
        self.refresh_token = os.getenv(
            "EBAY_USER_REFRESH_TOKEN",
            "",
        ).strip()
        self.static_access_token = os.getenv(
            "EBAY_USER_ACCESS_TOKEN",
            "",
        ).strip()
        self.legacy_auth_token = os.getenv(
            "EBAY_AUTH_TOKEN",
            "",
        ).strip()
        self.scope = os.getenv(
            "EBAY_USER_SCOPE",
            DEFAULT_SCOPE,
        ).strip()
        self.site_id = os.getenv(
            "EBAY_TRADING_SITE_ID",
            "3",
        ).strip()
        self.compatibility = os.getenv(
            "EBAY_TRADING_COMPATIBILITY_LEVEL",
            "1455",
        ).strip()
        self.timeout = int(
            os.getenv("EBAY_WATCHLIST_TIMEOUT_SECONDS", "30")
        )
        self.batch_size = max(
            1,
            min(
                100,
                int(os.getenv("EBAY_WATCHLIST_BATCH_SIZE", "25")),
            ),
        )
        self.session = requests.Session()
        self._access_token = ""
        self._access_token_expiry = 0.0

    @property
    def configured(self) -> bool:
        return bool(
            self.legacy_auth_token
            or self.static_access_token
            or (
                self.refresh_token
                and self.client_id
                and self.client_secret
            )
        )

    @property
    def authentication_mode(self) -> str:
        if self.refresh_token:
            return "OAuth refresh token"
        if self.static_access_token:
            return "OAuth user access token"
        if self.legacy_auth_token:
            return "Auth'n'Auth user token"
        return "not configured"

    def close(self) -> None:
        self.session.close()

    def _oauth_access_token(self) -> str:
        if self.static_access_token:
            return self.static_access_token

        if (
            self._access_token
            and time.time() < self._access_token_expiry - 60
        ):
            return self._access_token

        if not (
            self.refresh_token
            and self.client_id
            and self.client_secret
        ):
            raise RuntimeError(
                "An OAuth user refresh token and the production "
                "client credentials are required."
            )

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        # The scope is optional on refresh. Include it only when explicitly
        # configured so that an existing refresh token can retain its original
        # consented scopes by default.
        if self.scope:
            data["scope"] = self.scope

        response = self.session.post(
            OAUTH_TOKEN_ENDPOINT,
            auth=HTTPBasicAuth(
                self.client_id,
                self.client_secret,
            ),
            headers={
                "Content-Type":
                "application/x-www-form-urlencoded",
            },
            data=data,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                "Could not refresh the eBay user token: "
                f"HTTP {response.status_code} "
                f"{response.text[:700]}"
            )

        payload = response.json()
        self._access_token = str(
            payload.get("access_token", "")
        )
        self._access_token_expiry = (
            time.time() + int(payload.get("expires_in", 7200))
        )
        if not self._access_token:
            raise RuntimeError(
                "eBay did not return a user access token."
            )
        return self._access_token

    def _requester_credentials(self) -> str:
        if not self.legacy_auth_token:
            return ""
        return (
            "<RequesterCredentials>"
            f"<eBayAuthToken>{escape(self.legacy_auth_token)}</eBayAuthToken>"
            "</RequesterCredentials>"
        )

    def _call(
        self,
        call_name: str,
        inner_xml: str,
    ) -> WatchlistCallResult:
        if not self.configured:
            raise RuntimeError(
                "No user-authorised eBay Watchlist token is configured."
            )

        request_xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<{call_name}Request xmlns="{XML_NAMESPACE}">'
            f"{self._requester_credentials()}"
            f"{inner_xml}"
            f"</{call_name}Request>"
        )

        headers = {
            "Content-Type": "text/xml",
            "X-EBAY-API-CALL-NAME": call_name,
            "X-EBAY-API-SITEID": self.site_id,
            "X-EBAY-API-COMPATIBILITY-LEVEL":
                self.compatibility,
        }
        if not self.legacy_auth_token:
            headers["X-EBAY-API-IAF-TOKEN"] = (
                self._oauth_access_token()
            )

        response = self.session.post(
            TRADING_ENDPOINT,
            headers=headers,
            data=request_xml.encode("utf-8"),
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"{call_name} failed: HTTP "
                f"{response.status_code} "
                f"{response.text[:1000]}"
            )

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise RuntimeError(
                f"{call_name} returned invalid XML: {exc}"
            ) from exc

        acknowledgement = _xml_text(root, "Ack")
        errors = _response_errors(root)
        result = WatchlistCallResult(
            acknowledgement=acknowledgement,
            watchlist_count=_xml_int(root, "WatchListCount"),
            watchlist_maximum=_xml_int(root, "WatchListMaximum"),
            errors=errors,
        )

        if acknowledgement not in {"Success", "Warning"}:
            detail = "; ".join(errors) or "Unknown eBay error"
            raise RuntimeError(
                f"{call_name} returned "
                f"{acknowledgement or 'no acknowledgement'}: {detail}"
            )

        for warning in errors:
            self.logger.warning(
                "%s response: %s",
                call_name,
                warning,
            )
        return result

    def add_item_ids(
        self,
        item_ids: Iterable[str],
    ) -> list[tuple[list[str], WatchlistCallResult]]:
        unique = list(
            dict.fromkeys(
                str(value).strip()
                for value in item_ids
                if str(value).strip()
            )
        )
        output: list[
            tuple[list[str], WatchlistCallResult]
        ] = []

        for start in range(0, len(unique), self.batch_size):
            batch = unique[start:start + self.batch_size]
            inner = "".join(
                f"<ItemID>{escape(item_id)}</ItemID>"
                for item_id in batch
            )
            output.append(
                (batch, self._call("AddToWatchList", inner))
            )
        return output

    def remove_item_ids(
        self,
        item_ids: Iterable[str],
    ) -> list[tuple[list[str], WatchlistCallResult]]:
        unique = list(
            dict.fromkeys(
                str(value).strip()
                for value in item_ids
                if str(value).strip()
            )
        )
        output: list[
            tuple[list[str], WatchlistCallResult]
        ] = []

        for start in range(0, len(unique), self.batch_size):
            batch = unique[start:start + self.batch_size]
            inner = "".join(
                f"<ItemID>{escape(item_id)}</ItemID>"
                for item_id in batch
            )
            output.append(
                (batch, self._call("RemoveFromWatchList", inner))
            )
        return output

    def remove_all_items(self) -> WatchlistCallResult:
        return self._call(
            "RemoveFromWatchList",
            "<RemoveAllItems>true</RemoveAllItems>",
        )

    def _get_watchlist_page(
        self,
        page_number: int,
        entries_per_page: int = 200,
    ) -> tuple[list[str], int, int, int | None]:
        call_name = "GetMyeBayBuying"
        safe_page = max(1, int(page_number))
        safe_entries = max(1, min(200, int(entries_per_page)))
        inner_xml = (
            "<DetailLevel>ReturnAll</DetailLevel>"
            "<WatchList>"
            "<Include>true</Include>"
            "<Pagination>"
            f"<EntriesPerPage>{safe_entries}</EntriesPerPage>"
            f"<PageNumber>{safe_page}</PageNumber>"
            "</Pagination>"
            "</WatchList>"
        )

        request_xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<{call_name}Request xmlns="{XML_NAMESPACE}">'
            f"{self._requester_credentials()}"
            f"{inner_xml}"
            f"</{call_name}Request>"
        )
        headers = {
            "Content-Type": "text/xml",
            "X-EBAY-API-CALL-NAME": call_name,
            "X-EBAY-API-SITEID": self.site_id,
            "X-EBAY-API-COMPATIBILITY-LEVEL":
                self.compatibility,
        }
        if not self.legacy_auth_token:
            headers["X-EBAY-API-IAF-TOKEN"] = (
                self._oauth_access_token()
            )

        response = self.session.post(
            TRADING_ENDPOINT,
            headers=headers,
            data=request_xml.encode("utf-8"),
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                "GetMyeBayBuying failed: "
                f"HTTP {response.status_code} "
                f"{response.text[:1000]}"
            )

        root = ET.fromstring(response.content)
        acknowledgement = _xml_text(root, "Ack")
        if acknowledgement not in {"Success", "Warning"}:
            raise RuntimeError(
                "GetMyeBayBuying failed: "
                + ("; ".join(_response_errors(root)) or acknowledgement)
            )

        watchlist = root.find(
            f".//{{{XML_NAMESPACE}}}WatchList"
        )
        if watchlist is None:
            return [], 0, 0, None

        item_ids = [
            str(element.text or "").strip()
            for element in watchlist.findall(
                ".//"
                f"{{{XML_NAMESPACE}}}ItemArray/"
                f"{{{XML_NAMESPACE}}}Item/"
                f"{{{XML_NAMESPACE}}}ItemID"
            )
            if str(element.text or "").strip()
        ]

        total_pages_element = watchlist.find(
            f"{{{XML_NAMESPACE}}}PaginationResult/"
            f"{{{XML_NAMESPACE}}}TotalNumberOfPages"
        )
        total_entries_element = watchlist.find(
            f"{{{XML_NAMESPACE}}}PaginationResult/"
            f"{{{XML_NAMESPACE}}}TotalNumberOfEntries"
        )
        total_pages = (
            int(total_pages_element.text or 0)
            if total_pages_element is not None
            else 0
        )
        total_entries = (
            int(total_entries_element.text or 0)
            if total_entries_element is not None
            else len(item_ids)
        )

        maximum_text = _xml_text(root, "WatchListMaximum")
        maximum = int(maximum_text) if maximum_text.isdigit() else None
        return item_ids, total_pages, total_entries, maximum

    def get_watchlist_item_ids(self) -> tuple[list[str], int | None]:
        first_ids, total_pages, _, maximum = self._get_watchlist_page(1)
        all_ids = list(first_ids)

        for page_number in range(2, max(1, total_pages) + 1):
            page_ids, _, _, page_maximum = self._get_watchlist_page(
                page_number
            )
            all_ids.extend(page_ids)
            if maximum is None and page_maximum is not None:
                maximum = page_maximum

        return list(dict.fromkeys(all_ids)), maximum

    def get_watchlist_count(self) -> tuple[int, int | None]:
        _, _, total, maximum = self._get_watchlist_page(
            1,
            entries_per_page=1,
        )
        return total, maximum

    def clear_watchlist_robust(
        self,
    ) -> tuple[int, int, int | None, str]:
        """Clear the Watchlist, with a specific-item fallback.

        Returns: removed item count, remaining item count, maximum, method.
        """

        before_count, maximum = self.get_watchlist_count()
        if before_count == 0:
            return 0, 0, maximum, "already empty"

        try:
            result = self.remove_all_items()
            remaining = (
                result.watchlist_count
                if result.watchlist_count is not None
                else self.get_watchlist_count()[0]
            )
            return (
                max(0, before_count - remaining),
                remaining,
                result.watchlist_maximum or maximum,
                "RemoveAllItems",
            )
        except RuntimeError as exc:
            # Error 20820 is eBay's generic "nothing removed" response.
            # Fall back to reading the actual ItemIDs and removing them in
            # batches. This is also more diagnostic when the token belongs
            # to a different eBay account than expected.
            if "20820" not in str(exc):
                raise

            item_ids, fallback_maximum = self.get_watchlist_item_ids()
            if not item_ids:
                return 0, 0, fallback_maximum or maximum, "already empty"

            removed = 0
            failures: list[str] = []
            for start in range(0, len(item_ids), self.batch_size):
                batch = item_ids[start:start + self.batch_size]
                try:
                    self.remove_item_ids(batch)
                    removed += len(batch)
                except RuntimeError as batch_error:
                    # Retry one by one so a variation or stale listing cannot
                    # prevent ordinary watched listings from being removed.
                    for item_id in batch:
                        try:
                            self.remove_item_ids([item_id])
                            removed += 1
                        except RuntimeError as item_error:
                            failures.append(
                                f"{item_id}: {item_error}"
                            )

            remaining, final_maximum = self.get_watchlist_count()
            if remaining and failures:
                sample = "; ".join(failures[:5])
                raise RuntimeError(
                    f"Removed {removed} Watchlist item(s), but {remaining} "
                    f"remain. Some entries may be multi-variation or stale. "
                    f"Examples: {sample}"
                )

            return (
                removed,
                remaining,
                final_maximum or fallback_maximum or maximum,
                "specific ItemID fallback",
            )


class ManagedWatchlistLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {
            "version": 1,
            "items": {},
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
                self.data.setdefault("items", {})
        except (OSError, json.JSONDecodeError):
            backup = self.path.with_suffix(
                self.path.suffix + ".corrupt"
            )
            try:
                self.path.replace(backup)
            except OSError:
                pass

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

    @property
    def items(self) -> dict[str, dict[str, Any]]:
        return self.data.setdefault("items", {})

    def is_recent(
        self,
        legacy_item_id: str,
        recheck_hours: float,
    ) -> bool:
        record = self.items.get(legacy_item_id) or {}
        if not record.get("active"):
            return False
        value = str(record.get("last_confirmed", "") or "")
        if not value:
            return False
        try:
            confirmed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError:
            return False
        age = (
            datetime.now(timezone.utc) - confirmed
        ).total_seconds() / 3600
        return age <= recheck_hours

    def confirm(
        self,
        parsed: ParsedItemId,
        title: str,
        source: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.items.get(
            parsed.legacy_item_id,
            {},
        )
        self.items[parsed.legacy_item_id] = {
            "legacy_item_id": parsed.legacy_item_id,
            "browse_item_id": parsed.browse_item_id,
            "title": title,
            "source": source,
            "first_confirmed":
                existing.get("first_confirmed", now),
            "last_confirmed": now,
            "active": True,
        }

    def mark_removed(
        self,
        item_ids: Iterable[str],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for item_id in item_ids:
            record = self.items.get(str(item_id))
            if record is None:
                continue
            record["active"] = False
            record["removed_at"] = now

    def active_ids(self) -> list[str]:
        return [
            item_id
            for item_id, record in self.items.items()
            if bool(record.get("active"))
        ]


def _append_note(result: Any, text: str) -> None:
    current = str(getattr(result, "notes", "") or "").strip()
    if text in current:
        return
    setattr(
        result,
        "notes",
        f"{current}; {text}" if current else text,
    )


def sync_green_results(
    results: Iterable[Any],
    *,
    root: Path,
    source: str,
    logger: logging.Logger,
) -> WatchlistSyncSummary:
    """Add financially GREEN scanner results to the user's eBay Watchlist.

    Watchlist failure is deliberately non-fatal: the spreadsheet scan remains
    successful and the console/log explains what needs attention.
    """

    summary = WatchlistSyncSummary()
    if not env_bool("EBAY_WATCHLIST_ENABLED", True):
        summary.enabled = False
        summary.message = "EBAY_WATCHLIST_ENABLED is not YES."
        logger.info("eBay Watchlist sync: disabled.")
        return summary

    client = EbayWatchlistClient(logger)
    if not client.configured:
        summary.configured = False
        summary.message = (
            "Configure EBAY_USER_REFRESH_TOKEN, EBAY_USER_ACCESS_TOKEN, "
            "or EBAY_AUTH_TOKEN in .env."
        )
        logger.warning(
            "eBay Watchlist sync skipped: no user-authorised token "
            "is configured. Run configure-ebay-watchlist-auth.bat."
        )
        client.close()
        return summary

    ledger = ManagedWatchlistLedger(
        root / "data" / "ebay-watchlist-managed.json"
    )
    max_per_run = max(
        0,
        int(os.getenv("EBAY_WATCHLIST_MAX_ADD_PER_RUN", "50")),
    )
    recheck_hours = max(
        0.0,
        float(os.getenv("EBAY_WATCHLIST_RECHECK_HOURS", "6")),
    )

    candidates: list[tuple[Any, ParsedItemId]] = []
    seen: set[str] = set()
    now = datetime.now(timezone.utc)

    for result in results:
        if str(getattr(result, "decision", "")).upper() != "GREEN":
            continue
        summary.green_candidates += 1

        parsed = parse_item_id(getattr(result, "item_id", ""))
        if parsed is None:
            summary.failed += 1
            _append_note(
                result,
                "eBay Watchlist: unsupported item identifier",
            )
            continue

        if parsed.is_multi_variation:
            summary.skipped_variations += 1
            _append_note(
                result,
                "eBay Watchlist: skipped multi-variation listing",
            )
            continue

        end_time = getattr(result, "end_time", None)
        if isinstance(end_time, datetime):
            comparable = (
                end_time
                if end_time.tzinfo
                else end_time.replace(tzinfo=timezone.utc)
            )
            if comparable <= now:
                summary.skipped_expired += 1
                _append_note(
                    result,
                    "eBay Watchlist: listing already ended",
                )
                continue

        if parsed.legacy_item_id in seen:
            continue
        seen.add(parsed.legacy_item_id)

        if ledger.is_recent(
            parsed.legacy_item_id,
            recheck_hours,
        ):
            summary.already_recent += 1
            _append_note(
                result,
                "eBay Watchlist: already managed",
            )
            continue

        candidates.append((result, parsed))

    if max_per_run:
        candidates = candidates[:max_per_run]
    else:
        candidates = []

    summary.requested = len(candidates)
    if not candidates:
        summary.message = "No new eligible GREEN listings."
        logger.info(
            "eBay Watchlist sync: no new eligible GREEN listings."
        )
        client.close()
        ledger.save()
        return summary

    by_id = {
        parsed.legacy_item_id: (result, parsed)
        for result, parsed in candidates
    }

    confirmed_this_run: set[str] = set()

    try:
        for batch, call_result in client.add_item_ids(
            by_id.keys()
        ):
            summary.watchlist_count = call_result.watchlist_count
            summary.watchlist_maximum = (
                call_result.watchlist_maximum
            )
            for legacy_item_id in batch:
                result, parsed = by_id[legacy_item_id]
                ledger.confirm(
                    parsed,
                    str(getattr(result, "title", "") or ""),
                    source,
                )
                summary.confirmed += 1
                confirmed_this_run.add(legacy_item_id)
                _append_note(
                    result,
                    "eBay Watchlist: added/confirmed",
                )

            if (
                call_result.watchlist_count is not None
                and call_result.watchlist_maximum is not None
                and call_result.watchlist_count
                >= call_result.watchlist_maximum
            ):
                logger.warning(
                    "The eBay Watchlist is full at %s/%s.",
                    call_result.watchlist_count,
                    call_result.watchlist_maximum,
                )
                break

        summary.message = "Watchlist synchronisation completed."
    except Exception as exc:
        unconfirmed = [
            item_id
            for item_id in by_id
            if item_id not in confirmed_this_run
        ]
        summary.failed += len(unconfirmed)
        for item_id in unconfirmed:
            result, _ = by_id[item_id]
            _append_note(
                result,
                "eBay Watchlist: sync failed",
            )
        summary.message = str(exc)
        logger.error(
            "eBay Watchlist sync failed, but the scanner results "
            "will still be saved: %s",
            exc,
        )
    finally:
        ledger.save()
        client.close()

    logger.info(
        "eBay Watchlist sync: %s",
        summary.display,
    )
    return summary
