from __future__ import annotations
import argparse,json,os
from pathlib import Path
from dotenv import load_dotenv
from app.cache import SearchCache
from app.demo_data import demo_items
from app.ebay_client import EbayClient
from app.price_catalog import PriceCatalog
from app.scoring import evaluate
from app.workbook_adapter import ExcelWorkbookAdapter

def main()->int:
    parser=argparse.ArgumentParser(description="Pokemon eBay sniping scanner")
    parser.add_argument("--demo",action="store_true")
    parser.add_argument("--no-cache",action="store_true")
    args=parser.parse_args()

    root=Path(__file__).resolve().parent
    load_dotenv(root/".env")
    config=json.loads((root/"config.json").read_text(encoding="utf-8"))
    workbook=os.getenv("WORKBOOK_PATH",str(root/"Pokemon-Auction-Scanner-Dashboard.xlsx"))
    excel=ExcelWorkbookAdapter(workbook)
    cache=None
    try:
        searches=excel.read_sniping_searches(100)
        catalog=PriceCatalog(excel.read_price_records())
        opportunities=[]; reviews=[]; seen=set(); raw_count=0

        if args.demo:
            selected=searches[0] if searches else None
            batches=[(selected,demo_items())] if selected else []
            mode="SNIPE-DEMO"
        else:
            if not args.no_cache:
                cache=SearchCache(str(root/"data"/"sniping-search-cache.sqlite"),
                                  int(config.get("cache_ttl_minutes",45)))
            client=EbayClient(cache=cache,
                retry_attempts=int(config.get("retry_attempts",4)),
                delay_seconds=float(config.get("request_delay_seconds",.15)))
            batches=[(s,client.search_auctions(s.query,int(config.get("results_per_search",20))))
                     for s in searches]
            mode="SNIPE-LIVE"

        for search,items in batches:
            if search is None: continue
            raw_count+=len(items)
            for item in items:
                item_id=str(item.get("itemId",""))
                if not item_id or item_id in seen: continue
                seen.add(item_id)
                opp,review=evaluate(item,search.title,search.score,catalog,config)
                if opp: opportunities.append(opp)
                if review: reviews.append(review)

        opportunities.sort(key=lambda o:(o.decision!="GREEN",-o.score,o.hours_remaining))
        excel.write_snipe_queue(opportunities[:500])
        excel.append_log(mode,len(searches),raw_count,len(seen),
                         sum(o.decision=="GREEN" for o in opportunities),
                         sum(o.decision=="AMBER" for o in opportunities),
                         f"Sniping scan complete: {len(opportunities)} queue items; {len(reviews)} need review")
        print(f"Updated Snipe Queue: {len(opportunities)} items.")
        return 0
    except Exception as exc:
        try: excel.append_log("SNIPE-ERROR",0,0,0,0,0,repr(exc))
        except Exception: pass
        raise
    finally:
        if cache: cache.close()
        excel.close(save=True)

if __name__=="__main__":
    raise SystemExit(main())
