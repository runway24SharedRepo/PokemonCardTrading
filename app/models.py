from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class SearchDefinition:
    rank: int
    score: float
    title: str
    query: str

@dataclass(frozen=True)
class PriceRecord:
    card_name: str
    set_name: str
    card_number: str
    variant: str
    language: str
    condition: str
    market_value: float
    source: str
    source_date: str

@dataclass(frozen=True)
class CardMatch:
    display_name: str
    confidence: float
    market_value: float
    reason: str
    record: PriceRecord | None

@dataclass
class Opportunity:
    item_id: str
    title: str
    item_url: str
    image_url: str
    current_bid: float
    postage: float
    delivered_cost: float
    market_value: float
    ratio: float
    target_75: float
    maximum_bid: float
    headroom: float
    end_time: datetime
    hours_remaining: float
    bid_count: int
    seller: str
    feedback_percent: float
    feedback_count: int
    condition: str
    match_confidence: float
    search_source: str
    card_match: str
    decision: str
    score: float
    match_reason: str

@dataclass
class ReviewItem:
    priority: str
    reason: str
    title: str
    likely_card: str
    match_confidence: float
    current_bid: float
    postage: float
    delivered_cost: float
    possible_market: float
    end_time: datetime
    hours_remaining: float
    seller: str
    feedback_percent: float
    feedback_count: int
    condition: str
    search_source: str
    item_id: str
    item_url: str
    image_url: str
