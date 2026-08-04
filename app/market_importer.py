from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED = ["Card Name","Market Value (£)"]

def _key(row: dict[str,Any]) -> tuple[str,...]:
    return tuple(str(row.get(k,"")).strip().lower() for k in
                 ["Card Name","Set Name","Card Number","Variant","Language","Condition"])

def import_csv_into_excel(adapter, csv_path: str) -> dict[str,Any]:
    path=Path(csv_path)
    if not path.exists():
        return {"read":0,"imported":0,"rejected":0,"replaced":0,"message":"File not found"}
    with path.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    valid=[]; rejected=0
    for row in rows:
        if not all(str(row.get(k,"")).strip() for k in REQUIRED):
            rejected+=1; continue
        try: value=float(str(row["Market Value (£)"]).replace("£","").replace(",",""))
        except ValueError:
            rejected+=1; continue
        if value<=0:
            rejected+=1; continue
        row["Market Value (£)"]=value
        valid.append(row)
    result=adapter.replace_market_records(valid)
    result.update({"read":len(rows),"rejected":rejected,"file":str(path)})
    return result
