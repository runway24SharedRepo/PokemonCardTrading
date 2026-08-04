from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .ebay_client import parse_end_time
from .models import Opportunity, ReviewItem
from .price_catalog import PriceCatalog
from .title_parser import parse_title

def money(node: Any) -> float:
    if not isinstance(node, dict): return 0.0
    try: return float(node.get("value",0) or 0)
    except (TypeError,ValueError): return 0.0

def shipping_cost(item: dict[str,Any]) -> tuple[float,bool]:
    options = item.get("shippingOptions") or []
    vals = [money(o.get("shippingCost")) for o in options if isinstance(o,dict)]
    vals = [v for v in vals if v >= 0]
    return (min(vals), True) if vals else (0.0, False)

def evaluate(item: dict[str,Any], search_title: str, search_score: float,
             catalog: PriceCatalog, config: dict[str,Any]) -> tuple[Opportunity|None, ReviewItem|None]:
    title = str(item.get("title",""))
    lower = title.lower()
    if any(term.lower() in lower for term in config.get("exclude_terms",[])):
        return None, None
    match = catalog.match(title)
    bid = money(item.get("currentBidPrice") or item.get("price"))
    postage, shipping_known = shipping_cost(item)
    delivered = bid + postage
    end_time = parse_end_time(item.get("itemEndDate"))
    hours = max(0.0,(end_time-datetime.now(timezone.utc)).total_seconds()/3600)
    if hours > float(config["ending_within_hours"]) or delivered > float(config["maximum_delivered_cost_gbp"]):
        return None, None
    seller = item.get("seller") or {}
    feedback_percent = float(seller.get("feedbackPercentage") or 0)
    feedback_count = int(seller.get("feedbackScore") or 0)
    condition = str(item.get("condition") or "Unknown")
    image = item.get("image") or {}
    common = dict(
        title=title,current_bid=bid,postage=postage,delivered_cost=delivered,end_time=end_time,
        hours_remaining=hours,seller=str(seller.get("username","")),
        feedback_percent=feedback_percent,feedback_count=feedback_count,condition=condition,
        search_source=search_title,item_id=str(item.get("itemId","")),
        item_url=str(item.get("itemWebUrl","")),image_url=str(image.get("imageUrl",""))
    )
    reasons = []
    if match.confidence < float(config["minimum_match_confidence"]): reasons.append("low card-match confidence")
    if match.market_value < float(config["minimum_market_value_gbp"]): reasons.append("missing/low market reference")
    if not shipping_known: reasons.append("postage not supplied by API")
    parsed = parse_title(title)
    if parsed.stated_condition in ("damaged","played"): reasons.append(f"title states {parsed.stated_condition}")
    if reasons:
        priority = "HIGH" if match.market_value >= 20 or bid >= 15 else "NORMAL"
        return None, ReviewItem(priority, "; ".join(reasons), likely_card=match.display_name,
            match_confidence=match.confidence, possible_market=match.market_value, **common)

    market = match.market_value
    ratio = delivered / market if market else 99
    green, amber = float(config["green_ratio"]), float(config["amber_ratio"])
    decision = "GREEN" if ratio <= green else "AMBER" if ratio <= amber else "RED"
    seller_penalty = (8 if feedback_percent < float(config["minimum_seller_feedback_percent"]) else 0)
    seller_penalty += (6 if feedback_count < int(config["minimum_seller_feedback_count"]) else 0)
    condition_penalty = 10 if parsed.stated_condition == "lightly played" else 0
    discount_score = max(0,min(55,(1-ratio)*100))
    urgency_score = max(0,15-min(hours,48)/48*15)
    match_score = match.confidence * 15
    score = max(0,min(100,discount_score+urgency_score+search_score*.20+match_score
                         -seller_penalty-condition_penalty))
    target = market * green
    max_bid = max(0,target-postage)
    opp = Opportunity(
        item_id=common["item_id"],title=title,item_url=common["item_url"],image_url=common["image_url"],
        current_bid=bid,postage=postage,delivered_cost=delivered,market_value=market,
        ratio=ratio,target_75=target,maximum_bid=max_bid,headroom=max_bid-bid,end_time=end_time,
        hours_remaining=hours,bid_count=int(item.get("bidCount") or 0),seller=common["seller"],
        feedback_percent=feedback_percent,feedback_count=feedback_count,condition=condition,
        match_confidence=match.confidence,search_source=search_title,card_match=match.display_name,
        decision=decision,score=score,match_reason=match.reason)
    return opp, None
