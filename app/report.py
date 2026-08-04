from __future__ import annotations
from datetime import datetime
from html import escape
from pathlib import Path

def generate_report(path: str, opportunities: list, reviews: list) -> None:
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    for o in opportunities[:50]:
        rows.append(f"""<tr class="{o.decision.lower()}"><td>{o.score:.1f}</td><td>{escape(o.decision)}</td>
        <td>{escape(o.card_match)}</td><td>{escape(o.title)}</td><td>£{o.delivered_cost:.2f}</td>
        <td>£{o.market_value:.2f}</td><td>£{o.headroom:.2f}</td><td>{o.hours_remaining:.1f}h</td>
        <td><a href="{escape(o.item_url)}">Open eBay</a></td></tr>""")
    html=f"""<!doctype html><html><head><meta charset="utf-8"><title>Pokémon Auction Scanner</title>
    <style>body{{font-family:Segoe UI,Arial;margin:24px;background:#f5f7fa;color:#1f2937}}
    table{{border-collapse:collapse;width:100%;background:white}}th,td{{padding:8px;border:1px solid #ddd}}
    th{{background:#1f4e78;color:white}}tr.green{{background:#dff4df}}tr.amber{{background:#fff1bd}}
    tr.red{{background:#ffdede}}.kpi{{display:inline-block;background:white;padding:12px 20px;margin:5px;
    border-radius:8px;box-shadow:0 1px 4px #bbb}}</style></head><body>
    <h1>Pokémon Auction Scanner</h1><p>Generated {datetime.now():%Y-%m-%d %H:%M}</p>
    <div class="kpi">Opportunities: <b>{len(opportunities)}</b></div>
    <div class="kpi">GREEN: <b>{sum(o.decision=="GREEN" for o in opportunities)}</b></div>
    <div class="kpi">Review queue: <b>{len(reviews)}</b></div>
    <h2>Best opportunities</h2><table><tr><th>Score</th><th>Decision</th><th>Card</th>
    <th>Listing</th><th>Delivered</th><th>Market</th><th>Headroom</th><th>Ends</th><th>Link</th></tr>
    {''.join(rows)}</table></body></html>"""
    Path(path).write_text(html,encoding="utf-8")
