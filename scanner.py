from __future__ import annotations
import argparse,json,os
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv
from app.cache import SearchCache
from app.demo_data import demo_items
from app.ebay_client import EbayClient
from app.history import HistoryStore
from app.market_importer import import_csv_into_excel
from app.price_catalog import PriceCatalog
from app.report import generate_report
from app.scoring import evaluate
from app.workbook_adapter import ExcelWorkbookAdapter

def main()->int:
    p=argparse.ArgumentParser(description="Automated eBay UK Pokemon auction scanner")
    p.add_argument("--demo",action="store_true")
    p.add_argument("--no-cache",action="store_true")
    args=p.parse_args()
    root=Path(__file__).resolve().parent
    load_dotenv(root/".env")
    config=json.loads((root/"config.json").read_text(encoding="utf-8"))
    workbook=os.getenv("WORKBOOK_PATH",str(root/"Pokemon-Auction-Scanner-Dashboard.xlsx"))
    excel=ExcelWorkbookAdapter(workbook)
    cache=None
    history=HistoryStore(str(root/config["history_database_path"]))
    try:
        if config.get("automatic_market_csv_import",True):
            result=import_csv_into_excel(excel,str(root/config["market_import_path"]))
            excel.append_price_import_log(result)
        searches=excel.read_searches(int(config["maximum_searches_per_run"]))
        catalog=PriceCatalog(excel.read_price_records())
        if config.get("archive_previous_live_results",True): excel.archive_live()
        opportunities=[]; reviews=[]; raw_count=0; seen=set()
        per_search=defaultdict(lambda: {"raw":0,"unique":0,"opps":[],"reviews":[]})
        if args.demo:
            batches=[(searches[0] if searches else None,demo_items())]; mode="DEMO"
        else:
            if not args.no_cache:
                cache=SearchCache(str(root/"data"/"search-cache.sqlite"),
                                  int(config.get("cache_ttl_minutes",45)))
            client=EbayClient(cache=cache,retry_attempts=int(config.get("retry_attempts",4)),
                              delay_seconds=float(config.get("request_delay_seconds",.15)))
            batches=[(s,client.search_auctions(s.query,int(config["results_per_search"]))) for s in searches]
            mode="LIVE"
        for search,items in batches:
            if search is None: continue
            raw_count+=len(items); per_search[search.title]["raw"]+=len(items)
            local_seen=set()
            for item in items:
                iid=str(item.get("itemId",""))
                if not iid or iid in local_seen: continue
                local_seen.add(iid); per_search[search.title]["unique"]+=1
                if iid in seen: continue
                seen.add(iid)
                opp,review=evaluate(item,search.title,search.score,catalog,config)
                if opp:
                    opportunities.append(opp); per_search[search.title]["opps"].append(opp)
                if review:
                    reviews.append(review); per_search[search.title]["reviews"].append(review)
        opportunities.sort(key=lambda x:(x.decision!="GREEN",-x.score,x.hours_remaining))
        reviews.sort(key=lambda x:(x.priority!="HIGH",x.hours_remaining))
        opportunities=[o for o in opportunities if o.score>=float(config["minimum_score_shown"])]
        excel.write_opportunities(opportunities[:int(config["maximum_live_rows"])])
        excel.write_review_queue(reviews[:int(config["maximum_review_rows"])])
        excel.write_notifications(opportunities,float(config["notification_score_threshold"]),
                                  float(config["notification_headroom_threshold_gbp"]))
        history.save_listings(opportunities,reviews)
        for s in searches:
            stats=per_search[s.title]
            history.save_search_run(s,stats["raw"],stats["unique"],stats["opps"],stats["reviews"])
        history.purge(int(config["retain_history_days"]))
        excel.write_search_performance(history.performance())
        if config.get("generate_html_report",True):
            generate_report(str(root/config["report_path"]),opportunities,reviews)
        excel.append_log(mode,len(searches),raw_count,len(seen),
                         sum(o.decision=="GREEN" for o in opportunities),
                         sum(o.decision=="AMBER" for o in opportunities),
                         f"Completed: {len(opportunities)} scored; {len(reviews)} require review")
        print(f"Updated {workbook}: {len(opportunities)} opportunities, {len(reviews)} review items.")
        return 0
    except Exception as exc:
        try: excel.append_log("ERROR",0,0,0,0,0,repr(exc))
        except Exception: pass
        raise
    finally:
        if cache: cache.close()
        history.close()
        excel.close(save=True)
if __name__=="__main__": raise SystemExit(main())
