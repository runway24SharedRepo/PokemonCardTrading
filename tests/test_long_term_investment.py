from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from long_term_investment import (
    InvestmentContext,
    InvestmentSettings,
    PortfolioHolding,
    PriceHistoryStats,
    TargetOverride,
    assess_candidate,
    card_key,
)


def candidate(**overrides):
    values = {
        "card_id": "xy-p-xy41",
        "name": "Kyogre-EX",
        "set_name": "XY Black Star Promos",
        "number": "XY41",
        "variant": "Holofoil",
        "rarity": "Promo",
        "supertype": "Pokémon",
        "release_date": "2015-05-06",
        "market_value": 30.0,
        "price_change": 0.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_score_is_out_of_100_and_entry_discount_is_secondary():
    context = InvestmentContext()
    strong_entry = assess_candidate(candidate(), context, ratio=0.45, condition_flag="GREEN")
    weak_entry = assess_candidate(candidate(), context, ratio=0.95, condition_flag="GREEN")
    assert 0 <= strong_entry.long_term_score <= 100
    assert strong_entry.long_term_score - weak_entry.long_term_score <= 5
    assert strong_entry.acquisition_score == 5
    assert weak_entry.acquisition_score == 1


def test_old_promo_scores_above_recent_common():
    context = InvestmentContext()
    old_promo = assess_candidate(candidate(), context, ratio=0.7, condition_flag="GREEN")
    recent_common = assess_candidate(
        candidate(
            card_id="modern-common",
            name="Genericmon",
            set_name="Modern Set",
            number="12/100",
            rarity="Common",
            release_date=datetime.now(timezone.utc).date().isoformat(),
        ),
        context,
        ratio=0.7,
        condition_flag="GREEN",
    )
    assert old_promo.long_term_score > recent_common.long_term_score
    assert old_promo.reprint_score > recent_common.reprint_score


def test_condition_changes_long_term_score():
    context = InvestmentContext()
    clean = assess_candidate(candidate(), context, ratio=0.7, condition_flag="GREEN", condition_details="Near Mint")
    damaged = assess_candidate(candidate(), context, ratio=0.7, condition_flag="RED", condition_details="creased and damaged")
    assert clean.condition_score > damaged.condition_score
    assert clean.long_term_score > damaged.long_term_score


def test_price_history_can_raise_resilience_confidence():
    card = candidate()
    now = datetime.now(timezone.utc)
    context = InvestmentContext(
        history={
            card_key(card): PriceHistoryStats(
                values=[
                    (now - timedelta(days=90), 20),
                    (now - timedelta(days=45), 22),
                    (now, 24),
                ]
            )
        }
    )
    assessment = assess_candidate(card, context, ratio=0.7, condition_flag="GREEN")
    assert assessment.resilience_score >= 7
    assert assessment.data_confidence in {"MEDIUM", "HIGH"}


def test_manual_target_override_wins():
    card = candidate()
    context = InvestmentContext(
        overrides={
            card_key(card): TargetOverride(
                card_id=card.card_id,
                total_score=96,
                desired_max_ratio=0.82,
                minimum_hold_years=10,
                thesis="Manual research thesis.",
                risks="Manual research risks.",
            )
        }
    )
    assessment = assess_candidate(card, context, ratio=0.8, condition_flag="GREEN")
    assert assessment.long_term_score == 96
    assert assessment.investment_tier == "CORE ASSET"
    assert assessment.minimum_hold_years == 10
    assert assessment.thesis == "Manual research thesis."


def test_portfolio_target_prevents_automatic_accumulation():
    card = candidate()
    key = card_key(card)
    context = InvestmentContext(
        portfolio_by_card={
            key: PortfolioHolding(
                card_key=key,
                pokemon_key="kyogre",
                quantity=3,
                cost=60,
                current_value=90,
            )
        },
        total_portfolio_value=90,
    )
    assessment = assess_candidate(card, context, ratio=0.5, condition_flag="GREEN")
    assert assessment.portfolio_fit == "HOLDING TARGET REACHED"
    assert assessment.long_term_action == "HOLD — DO NOT ADD"
