import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT / "payload"
if not (PROJECT_ROOT / "on_demand_pricing.py").exists():
    raise RuntimeError("Phase 5.7.5 packaged payload is missing")
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import requests
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    class HTTPError(RequestException):
        pass

    class Session:
        def __init__(self):
            self.headers = {}

    requests_stub.RequestException = RequestException
    requests_stub.HTTPError = HTTPError
    requests_stub.Session = Session
    sys.modules["requests"] = requests_stub
    requests = requests_stub

from on_demand_pricing import OnDemandPriceResolver
from clear_on_demand_price_failures import clear_failure_checkpoints


class FakeResponse:
    headers = {}

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload, self.status_code)


class SequenceSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("No fake response remains")
        return self.responses.pop(0)


class RecordingLogger:
    def __init__(self):
        self.records = []

    def info(self, message, *args):
        self.records.append(("info", message % args if args else message))

    def warning(self, message, *args):
        self.records.append(("warning", message % args if args else message))


def palkia_payload():
    return {
        "data": {
            "id": "dp5-11",
            "name": "Palkia",
            "number": "11",
            "rarity": "Rare Holo",
            "set": {"id": "dp5", "name": "Majestic Dawn"},
            "tcgplayer": {
                "prices": {
                    "holofoil": {"market": 65.92},
                    "reverseHolofoil": {"market": 26.67},
                }
            },
            "cardmarket": {
                "updatedAt": "2026/08/05",
                "url": "https://prices.pokemontcg.io/cardmarket/dp5-11",
                "prices": {
                    "averageSellPrice": 15.03,
                    "trendPrice": 15.19,
                    "avg30": 14.00,
                    "reverseHoloAvg30": 10.00,
                },
            },
        }
    }


class OnDemandPricingTests(unittest.TestCase):
    def resolver(self, payload, *, root=None, status_code=200, extra_env=None):
        env = {
            "MARKET_EUR_TO_GBP_OVERRIDE": "0.85",
            "MARKET_USD_TO_GBP_OVERRIDE": "0.75",
            "ON_DEMAND_PRICE_RETRY_ATTEMPTS": "1",
        }
        env.update(extra_env or {})
        session = FakeSession(payload, status_code=status_code)
        context = patch.dict(os.environ, env, clear=False)
        context.start()
        self.addCleanup(context.stop)
        if root is None:
            temp = tempfile.TemporaryDirectory()
            self.addCleanup(temp.cleanup)
            root = Path(temp.name)
        resolver = OnDemandPriceResolver(
            root,
            session=session,
            sleep=lambda _: None,
        )
        # Cleanups run last-in, first-out. Register the SQLite close after the
        # temporary-directory cleanup so Windows releases the database first.
        self.addCleanup(resolver.close)
        return resolver, session

    def test_fetches_once_per_card_and_uses_only_30_day_fields(self):
        resolver, session = self.resolver(palkia_payload())
        holo = SimpleNamespace(
            card_id="dp5-11",
            variant="Holofoil",
            market_value=999.0,
            source="old static value",
            source_date=None,
            source_url="",
        )
        reverse = SimpleNamespace(
            card_id="dp5-11",
            variant="Reverse Holofoil",
            market_value=999.0,
            source="old static value",
            source_date=None,
            source_url="",
        )

        quote_holo = resolver.apply(holo)
        quote_reverse = resolver.apply(reverse)

        self.assertEqual(quote_holo.source_field, "cardmarket.prices.avg30")
        self.assertEqual(quote_holo.price_eur, 14.00)
        self.assertEqual(quote_holo.price_gbp, 11.90)
        self.assertEqual(holo.market_value, 11.90)
        self.assertEqual(
            quote_reverse.source_field,
            "cardmarket.prices.reverseHoloAvg30",
        )
        self.assertEqual(quote_reverse.price_gbp, 8.50)
        self.assertEqual(len(session.calls), 1)

    def test_unseparated_edition_never_uses_static_fallback(self):
        payload = palkia_payload()
        payload["data"]["tcgplayer"]["prices"] = {
            "1stEditionHolofoil": {"market": 120.00}
        }
        resolver, _ = self.resolver(payload)
        candidate = SimpleNamespace(
            card_id="dp5-11",
            variant="1st Edition Holofoil",
            market_value=999.0,
            source="old static value",
            source_date=None,
            source_url="",
        )

        quote = resolver.apply(candidate)

        self.assertFalse(quote.available)
        self.assertEqual(candidate.market_value, 0.0)
        self.assertIn("EDITION", quote.status)

    def test_pikachu_rejects_non_windowed_average_sell_price(self):
        payload = {
            "data": {
                "id": "base1-58",
                "name": "Pikachu",
                "number": "58",
                "rarity": "Common",
                "set": {"id": "base1", "name": "Base"},
                "tcgplayer": {"prices": {"unlimited": {"market": 99.0}}},
                "cardmarket": {
                    "updatedAt": "2026/08/06",
                    "url": "https://prices.pokemontcg.io/cardmarket/base1-58",
                    "prices": {
                        "averageSellPrice": 23.99,
                        "trendPrice": 20.00,
                        "avg30": 12.24,
                    },
                },
            }
        }
        resolver, _ = self.resolver(payload)
        candidate = SimpleNamespace(
            card_id="base1-58",
            variant="Normal",
            market_value=999.0,
            source="old static value",
            source_date=None,
            source_url="",
        )

        quote = resolver.apply(candidate)

        self.assertEqual(quote.source_field, "cardmarket.prices.avg30")
        self.assertEqual(quote.price_eur, 12.24)
        self.assertEqual(quote.price_gbp, 10.40)

    def test_success_is_reused_from_durable_24_hour_cache(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        first, first_session = self.resolver(palkia_payload(), root=root)
        first.quote("dp5-11", "Holofoil")
        first.close()

        second, second_session = self.resolver(
            {}, root=root, status_code=502
        )
        quote = second.quote("dp5-11", "Holofoil")

        self.assertTrue(quote.available)
        self.assertEqual(len(first_session.calls), 1)
        self.assertEqual(len(second_session.calls), 0)
        self.assertEqual(second.disk_cache_hits, 1)

    def test_transient_failure_gets_three_bounded_attempts_and_one_warning(self):
        resolver, session = self.resolver(
            {},
            status_code=502,
            extra_env={
                "ON_DEMAND_PRICE_RETRY_ATTEMPTS": "3",
                "ON_DEMAND_PRICE_FAILURE_COOLDOWN_SECONDS": "60",
            },
        )
        logger = RecordingLogger()
        resolver.logger = logger
        first = resolver.quote("bad-1", "Normal")
        second = resolver.quote("bad-1", "Holofoil")

        self.assertFalse(first.available)
        self.assertFalse(second.available)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(resolver.retry_calls, 2)
        self.assertEqual(resolver.retry_recoveries, 0)
        self.assertEqual(resolver.deferred_requests, 0)
        self.assertEqual(resolver.network_failures, 1)
        warnings = [text for level, text in logger.records if level == "warning"]
        self.assertEqual(len(warnings), 1)
        self.assertIn("all 3 attempts failed", warnings[0])

    def test_retry_recovers_a_temporary_502_and_caches_the_success(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        env = {
            "MARKET_EUR_TO_GBP_OVERRIDE": "0.85",
            "MARKET_USD_TO_GBP_OVERRIDE": "0.75",
            "ON_DEMAND_PRICE_RETRY_ATTEMPTS": "3",
        }
        context = patch.dict(os.environ, env, clear=False)
        context.start()
        self.addCleanup(context.stop)
        session = SequenceSession(
            [
                FakeResponse({}, 502),
                FakeResponse(palkia_payload(), 200),
            ]
        )
        resolver = OnDemandPriceResolver(root, session=session, sleep=lambda _: None)
        self.addCleanup(resolver.close)

        quote = resolver.quote("dp5-11", "Holofoil")

        self.assertTrue(quote.available)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(resolver.retry_calls, 1)
        self.assertEqual(resolver.retry_recoveries, 1)
        self.assertEqual(resolver.network_failures, 0)

        resolver.close()
        cached, cached_session = self.resolver({}, root=root, status_code=502)
        cached_quote = cached.quote("dp5-11", "Holofoil")
        self.assertTrue(cached_quote.available)
        self.assertEqual(len(cached_session.calls), 0)

    def test_third_attempt_uses_exact_id_collection_query(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        env = {
            "MARKET_EUR_TO_GBP_OVERRIDE": "0.85",
            "MARKET_USD_TO_GBP_OVERRIDE": "0.75",
            "ON_DEMAND_PRICE_RETRY_ATTEMPTS": "3",
        }
        context = patch.dict(os.environ, env, clear=False)
        context.start()
        self.addCleanup(context.stop)
        collection_payload = {"data": [palkia_payload()["data"]]}
        session = SequenceSession(
            [
                FakeResponse({}, 502),
                FakeResponse({}, 500),
                FakeResponse(collection_payload, 200),
            ]
        )
        logger = RecordingLogger()
        resolver = OnDemandPriceResolver(
            root, logger=logger, session=session, sleep=lambda _: None
        )
        self.addCleanup(resolver.close)

        quote = resolver.quote("dp5-11", "Holofoil")

        self.assertTrue(quote.available)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(session.calls[0][1]["params"]["select"],
                         "id,name,set,number,rarity,cardmarket,tcgplayer")
        self.assertIsNone(session.calls[1][1]["params"])
        self.assertTrue(session.calls[2][0].endswith("/v2/cards"))
        self.assertEqual(session.calls[2][1]["params"]["q"], "id:dp5-11")
        self.assertEqual(resolver.alternate_path_recoveries, 1)
        recovered = [
            text for level, text in logger.records
            if level == "info" and "PRICE RECOVERED" in text
        ]
        self.assertEqual(len(recovered), 1)
        self.assertIn("exact-ID query", recovered[0])

    def test_installer_migration_clears_failures_but_preserves_success_cache(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        resolver, _ = self.resolver(palkia_payload(), root=root)
        resolver.quote("dp5-11", "Holofoil")
        resolver.close()
        database = root / "data" / "on-demand-price-cache.sqlite"
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "INSERT INTO fetch_failure(card_id, failed_at, retry_after, attempts, last_error) "
                "VALUES('bad-1', 1, 9999999999, 1, 'HTTP 502')"
            )
            connection.commit()
        finally:
            connection.close()

        self.assertEqual(clear_failure_checkpoints(root), 1)

        connection = sqlite3.connect(database)
        try:
            failures = connection.execute("SELECT COUNT(*) FROM fetch_failure").fetchone()[0]
            successes = connection.execute("SELECT COUNT(*) FROM card_cache").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(failures, 0)
        self.assertEqual(successes, 1)

    def test_circuit_breaker_defers_remaining_uncached_cards(self):
        resolver, session = self.resolver(
            {},
            status_code=500,
            extra_env={
                "ON_DEMAND_PRICE_CIRCUIT_FAILURES": "2",
                "ON_DEMAND_PRICE_RETRY_ATTEMPTS": "3",
            },
        )
        resolver.quote("bad-1", "Normal")
        resolver.quote("bad-2", "Normal")
        resolver.quote("bad-3", "Normal")

        self.assertEqual(len(session.calls), 6)
        self.assertEqual(resolver.network_failures, 2)
        self.assertEqual(resolver.deferred_requests, 1)

    def test_stale_cache_is_not_used_when_refresh_fails(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        good, _ = self.resolver(palkia_payload(), root=root)
        good.quote("dp5-11", "Holofoil")
        good.close()
        database = root / "data" / "on-demand-price-cache.sqlite"
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "UPDATE card_cache SET fetched_at = fetched_at - 90000"
            )
            connection.commit()
        finally:
            # sqlite3.Connection.__exit__ commits or rolls back but does not
            # close. Windows keeps the database locked until close() is called.
            connection.close()

        failing, session = self.resolver({}, root=root, status_code=502)
        quote = failing.quote("dp5-11", "Holofoil")

        self.assertFalse(quote.available)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(failing.disk_cache_hits, 0)

        # Prove all database handles are released before temporary-directory
        # cleanup. A rename fails immediately on Windows if SQLite is open.
        failing.close()
        for sqlite_file in root.joinpath("data").glob(
            "on-demand-price-cache.sqlite*"
        ):
            probe = sqlite_file.with_name(sqlite_file.name + ".lock-check")
            sqlite_file.rename(probe)
            probe.rename(sqlite_file)

    def test_runtime_scripts_do_not_claim_static_prices_are_authoritative(self):
        root = PROJECT_ROOT
        for name in (
            "live_opportunity_radar.py",
            "random_range_sniper.py",
            "seller_radar.py",
        ):
            text = (root / name).read_text(encoding="utf-8")
            self.assertNotIn(
                "using the free Pokémon TCG market values already",
                text,
            )
            self.assertIn("OnDemandPriceResolver", text)
            self.assertIn("price_resolver.close()", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
