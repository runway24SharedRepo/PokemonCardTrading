from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Iterable
from .models import Opportunity, PriceRecord, ReviewItem, SearchDefinition

class ExcelWorkbookAdapter:
    def __init__(self, workbook_path: str) -> None:
        if not Path(workbook_path).exists(): raise FileNotFoundError(workbook_path)
        import win32com.client
        self.excel = win32com.client.DispatchEx("Excel.Application")
        self.excel.Visible = False
        self.excel.DisplayAlerts = False
        self.book = self.excel.Workbooks.Open(str(Path(workbook_path).resolve()))

    def close(self, save: bool=True) -> None:
        self.book.Close(SaveChanges=save); self.excel.Quit()

    def read_searches(self, limit: int) -> list[SearchDefinition]:
        ws=self.book.Worksheets("eBay Search Library"); out=[]; row=8
        while row<2000 and len(out)<limit:
            rank=ws.Cells(row,1).Value
            if rank in (None,""): break
            query=str(ws.Cells(row,6).Value or "").strip()
            if query:
                out.append(SearchDefinition(int(rank),float(ws.Cells(row,2).Value or 0),
                                            str(ws.Cells(row,3).Value or ""),query))
            row+=1
        return out

    def read_price_records(self) -> list[PriceRecord]:
        ws=self.book.Worksheets("Market Data Import"); out=[]; row=5
        while row<10000:
            enabled=ws.Cells(row,1).Value
            name=ws.Cells(row,2).Value
            if name in (None,""):
                row+=1
                if row>100: break
                continue
            if str(enabled or "YES").upper()=="YES":
                try: value=float(ws.Cells(row,8).Value or 0)
                except (TypeError,ValueError): value=0
                out.append(PriceRecord(
                    str(name),str(ws.Cells(row,3).Value or ""),str(ws.Cells(row,4).Value or ""),
                    str(ws.Cells(row,5).Value or ""),str(ws.Cells(row,6).Value or "English"),
                    str(ws.Cells(row,7).Value or "Near Mint"),value,
                    str(ws.Cells(row,9).Value or ""),str(ws.Cells(row,10).Text or "")
                ))
            row+=1
        return out

    def archive_live(self) -> None:
        src=self.book.Worksheets("Live Opportunities")
        dst=self.book.Worksheets("Opportunity Archive")
        last=src.Cells(src.Rows.Count,6).End(-4162).Row
        if last<5: return
        dest=dst.Cells(dst.Rows.Count,1).End(-4162).Row+1
        now=datetime.now()
        rows=[]
        for r in range(5,last+1):
            if not src.Cells(r,6).Value: continue
            vals=[src.Cells(r,c).Value for c in range(2,27)]
            rows.append([now,"EXPIRED/REFRESHED"]+vals)
        if rows:
            dst.Range(dst.Cells(dest,1),dst.Cells(dest+len(rows)-1,26)).Value=tuple(tuple(x) for x in rows)

    def write_opportunities(self, opportunities: Iterable[Opportunity]) -> None:
        ws=self.book.Worksheets("Live Opportunities"); ws.Range("A5:Z1000").ClearContents()
        rows=[]; now=datetime.now()
        for rank,o in enumerate(opportunities,start=1):
            rows.append([rank,round(o.score,1),o.decision,o.card_match,o.title,o.item_id,
                o.current_bid,o.postage,o.delivered_cost,o.market_value,o.ratio,o.target_75,
                o.maximum_bid,o.headroom,o.end_time.astimezone().replace(tzinfo=None),
                o.hours_remaining,o.bid_count,o.seller,o.feedback_percent/100,o.feedback_count,
                o.condition,o.match_confidence,o.search_source,o.item_url,o.image_url,now])
        if rows:
            ws.Range(ws.Cells(5,1),ws.Cells(4+len(rows),26)).Value=tuple(tuple(r) for r in rows)

    def write_review_queue(self, items: Iterable[ReviewItem]) -> None:
        ws=self.book.Worksheets("Review Queue"); ws.Range("A5:S1000").ClearContents()
        rows=[]; now=datetime.now()
        for x in items:
            rows.append([x.priority,x.reason,x.title,x.likely_card,x.match_confidence,x.current_bid,
                x.postage,x.delivered_cost,x.possible_market,
                x.end_time.astimezone().replace(tzinfo=None),x.hours_remaining,x.seller,
                x.feedback_percent/100,x.feedback_count,x.condition,x.search_source,x.item_id,
                x.item_url,x.image_url])
        if rows:
            ws.Range(ws.Cells(5,1),ws.Cells(4+len(rows),19)).Value=tuple(tuple(r) for r in rows)
        # Preserve user-owned Status/Notes columns T:U.


    def replace_market_records(self, rows: list[dict]) -> dict:
        ws=self.book.Worksheets("Market Data Import")
        existing={}
        row=5
        while row<10000:
            name=ws.Cells(row,2).Value
            if not name:
                row+=1
                if row>100: break
                continue
            key=tuple(str(ws.Cells(row,c).Value or "").strip().lower() for c in [2,3,4,5,6,7])
            existing[key]=row
            row+=1
        imported=0; replaced=0
        for item in rows:
            key=tuple(str(item.get(k,"")).strip().lower() for k in
                      ["Card Name","Set Name","Card Number","Variant","Language","Condition"])
            target=existing.get(key)
            if target:
                replaced+=1
            else:
                target=ws.Cells(ws.Rows.Count,2).End(-4162).Row+1
                if target<5: target=5
                existing[key]=target
            values=((
              str(item.get("Enabled","YES") or "YES"),str(item.get("Card Name","")),
              str(item.get("Set Name","")),str(item.get("Card Number","")),
              str(item.get("Variant","")),str(item.get("Language","English") or "English"),
              str(item.get("Condition","Near Mint") or "Near Mint"),
              float(item.get("Market Value (£)",0)),str(item.get("Source","CSV import")),
              str(item.get("Source Date","")),str(item.get("Source URL","")),
              str(item.get("Notes",""))
            ),)
            ws.Range(ws.Cells(target,1),ws.Cells(target,12)).Value=values
            imported+=1
        return {"imported":imported,"replaced":replaced}

    def append_price_import_log(self, result: dict) -> None:
        ws=self.book.Worksheets("Price Import Log")
        row=ws.Cells(ws.Rows.Count,1).End(-4162).Row+1
        ws.Range(ws.Cells(row,1),ws.Cells(row,8)).Value=((
          datetime.now(),result.get("file",""),result.get("read",0),result.get("imported",0),
          result.get("rejected",0),result.get("replaced",0),"CSV",
          result.get("message","Completed")
        ),)

    def write_search_performance(self, rows: list[dict]) -> None:
        ws=self.book.Worksheets("Search Performance")
        ws.Range("A5:P1000").ClearContents()
        values=[]
        for x in rows:
            values.append([x["rank"],x["base_score"],x["effective_score"],x["title"],x["query"],
              x["runs"],x["raw"],x["unique"],x["opportunities"],x["green"],x["amber"],x["review"],
              x["green_rate"],x["useful_rate"],x["avg_discount"],x["last_success"] or ""])
        if values:
            ws.Range(ws.Cells(5,1),ws.Cells(4+len(values),16)).Value=tuple(tuple(r) for r in values)

    def write_notifications(self, opportunities: list, score_threshold: float, headroom_threshold: float) -> None:
        ws=self.book.Worksheets("Notification Queue")
        # Preserve acknowledged rows; replace only unacknowledged scanner-generated rows.
        ws.Range("A4:M1000").ClearContents()
        rows=[]; now=datetime.now()
        for o in opportunities:
            if o.decision=="GREEN" and o.score>=score_threshold and o.headroom>=headroom_threshold:
                rows.append(["HIGH","GREEN",o.score,o.card_match,o.title,o.delivered_cost,o.market_value,
                  o.headroom,o.hours_remaining,o.seller,
                  f"Score {o.score:.1f}; headroom £{o.headroom:.2f}; match {o.match_confidence:.0%}",
                  o.item_url,now])
        if rows:
            ws.Range(ws.Cells(4,1),ws.Cells(3+len(rows),13)).Value=tuple(tuple(r) for r in rows)
            for r in range(4,4+len(rows)):
                if not ws.Cells(r,14).Value: ws.Cells(r,14).Value="NO"


    def read_sniping_searches(self, limit: int = 100) -> list[SearchDefinition]:
        ws=self.book.Worksheets("Sniping Search Library")
        out=[]; row=23
        while row<=122 and len(out)<limit:
            rank=ws.Cells(row,1).Value
            if rank in (None,""): break
            enabled=str(ws.Cells(row,18).Value or "NO").upper()
            query=str(ws.Cells(row,9).Value or "").strip()
            if enabled=="YES" and query:
                out.append(SearchDefinition(
                    int(rank),float(ws.Cells(row,2).Value or 0),
                    str(ws.Cells(row,3).Value or ""),query
                ))
            row+=1
        return out

    def write_snipe_queue(self, opportunities: Iterable[Opportunity]) -> None:
        ws=self.book.Worksheets("Snipe Queue")
        ws.Range("A5:Y505").ClearContents()
        rows=[]
        for priority,o in enumerate(opportunities,start=1):
            rows.append([
              priority,o.decision,round(o.score,1),o.card_match,o.title,o.item_id,
              o.current_bid,o.postage,o.delivered_cost,o.market_value,o.ratio,
              o.target_75,o.maximum_bid,o.headroom,
              o.end_time.astimezone().replace(tzinfo=None),
              max(0,round(o.hours_remaining*60)),o.bid_count,o.seller,
              o.feedback_percent/100,o.feedback_count,o.condition,o.match_confidence,
              o.search_source,o.item_url,o.image_url
            ])
        if rows:
            ws.Range(ws.Cells(5,1),ws.Cells(4+len(rows),25)).Value=tuple(tuple(r) for r in rows)
        # User-owned Status and Notes columns Z:AA are preserved.

    def append_log(self, mode:str,searches:int,raw:int,unique:int,green:int,amber:int,message:str)->None:
        ws=self.book.Worksheets("Scanner Log")
        row=ws.Cells(ws.Rows.Count,1).End(-4162).Row+1
        ws.Range(ws.Cells(row,1),ws.Cells(row,8)).Value=((
            datetime.now(),mode,searches,raw,unique,green,amber,message),)
