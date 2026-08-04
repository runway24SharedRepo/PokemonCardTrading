from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from .models import Opportunity, ReviewItem, SearchDefinition

class HistoryStore:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS listing_history(
          seen_at TEXT,item_id TEXT,title TEXT,search_title TEXT,score REAL,decision TEXT,
          delivered REAL,market REAL,headroom REAL,hours_remaining REAL,match_confidence REAL,
          PRIMARY KEY(seen_at,item_id,search_title))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS search_runs(
          run_at TEXT,search_rank INTEGER,base_score REAL,search_title TEXT,query TEXT,
          raw_results INTEGER,unique_results INTEGER,opportunities INTEGER,green INTEGER,
          amber INTEGER,review_items INTEGER,avg_discount REAL)""")
        self.db.commit()

    def save_listings(self, opportunities: Iterable[Opportunity], reviews: Iterable[ReviewItem]) -> None:
        now=datetime.now(timezone.utc).isoformat()
        for o in opportunities:
            self.db.execute("""INSERT OR IGNORE INTO listing_history VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (now,o.item_id,o.title,o.search_source,o.score,o.decision,o.delivered_cost,
                 o.market_value,o.headroom,o.hours_remaining,o.match_confidence))
        for r in reviews:
            self.db.execute("""INSERT OR IGNORE INTO listing_history VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (now,r.item_id,r.title,r.search_source,0,"REVIEW",r.delivered_cost,
                 r.possible_market,0,r.hours_remaining,r.match_confidence))
        self.db.commit()

    def save_search_run(self, search: SearchDefinition, raw: int, unique: int, opportunities: list[Opportunity],
                        reviews: list[ReviewItem]) -> None:
        discounts=[1-o.ratio for o in opportunities if o.market_value>0]
        self.db.execute("""INSERT INTO search_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
          (datetime.now(timezone.utc).isoformat(),search.rank,search.score,search.title,search.query,
           raw,unique,len(opportunities),sum(o.decision=="GREEN" for o in opportunities),
           sum(o.decision=="AMBER" for o in opportunities),len(reviews),
           sum(discounts)/len(discounts) if discounts else 0))
        self.db.commit()

    def performance(self) -> list[dict]:
        rows=self.db.execute("""SELECT MIN(search_rank),MAX(base_score),search_title,MAX(query),
          COUNT(*),SUM(raw_results),SUM(unique_results),SUM(opportunities),SUM(green),SUM(amber),
          SUM(review_items),AVG(avg_discount),MAX(CASE WHEN green>0 THEN run_at END)
          FROM search_runs GROUP BY search_title ORDER BY MIN(search_rank)""").fetchall()
        out=[]
        for r in rows:
            runs=max(r[4] or 0,1); raw=max(r[5] or 0,0); unique=max(r[6] or 0,0)
            opportunities=max(r[7] or 0,0); green=max(r[8] or 0,0)
            green_rate=green/max(opportunities,1)
            useful_rate=opportunities/max(unique,1)
            effective=max(0,min(100,float(r[1] or 0)+green_rate*18+useful_rate*12-(r[10] or 0)/runs*1.5))
            out.append({"rank":r[0],"base_score":r[1],"effective_score":effective,"title":r[2],"query":r[3],
              "runs":r[4],"raw":r[5] or 0,"unique":r[6] or 0,"opportunities":opportunities,
              "green":green,"amber":r[9] or 0,"review":r[10] or 0,"green_rate":green_rate,
              "useful_rate":useful_rate,"avg_discount":r[11] or 0,"last_success":r[12]})
        return out

    def purge(self, retain_days: int) -> None:
        cutoff=(datetime.now(timezone.utc)-timedelta(days=retain_days)).isoformat()
        self.db.execute("DELETE FROM listing_history WHERE seen_at<?",(cutoff,))
        self.db.execute("DELETE FROM search_runs WHERE run_at<?",(cutoff,))
        self.db.commit()

    def close(self) -> None:
        self.db.close()
