from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

from ai_market_pricer import AIListingMarketPricer


def main() -> int:
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env", override=True, encoding="utf-8-sig")
    candidate = SimpleNamespace(
        card_id="base1-58",
        name="Pikachu",
        set_name="Base",
        number="58",
        variant="Normal",
        market_value=0.0,
        source="",
        source_date="",
        source_url="",
    )
    pricer = AIListingMarketPricer(root)
    try:
        estimate = pricer.price(
            candidate,
            "Pokemon Base Set Pikachu 58/102 Unlimited raw card",
            "PHASE5631-SMOKE-TEST",
            "",
        )
        print("AI MARKET PRICER TEST SUCCESSFUL")
        print(f"Value: GBP {estimate.value_gbp:.2f}")
        print(f"Confidence: {estimate.confidence}")
        print(f"Method: {estimate.method}")
        print(f"Evidence count: {estimate.evidence_count}")
        print(f"Cached: {'YES' if estimate.cached else 'NO'}")
        return 0
    except Exception as exc:
        print("AI MARKET PRICER TEST FAILED")
        print(str(exc))
        return 1
    finally:
        pricer.close()


if __name__ == "__main__":
    raise SystemExit(main())
