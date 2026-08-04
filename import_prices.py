from __future__ import annotations
import argparse,csv
from pathlib import Path
def main():
    p=argparse.ArgumentParser(description="Normalise a HoloDex-style CSV for Market Data Import")
    p.add_argument("input_csv"); p.add_argument("-o","--output",default="data/market-import.csv")
    a=p.parse_args()
    src=Path(a.input_csv); out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    with src.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    headers=["Enabled","Card Name","Set Name","Card Number","Variant","Language","Condition",
             "Market Value (£)","Source","Source Date","Source URL","Notes"]
    with out.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f); w.writerow(headers)
        for r in rows:
            raw=r.get("Market Price (As of 2026-08-02)") or r.get("Market Price") or "0"
            try: value=float(raw)/100
            except ValueError: value=0
            w.writerow(["YES",r.get("Product Name",""),r.get("Set Name",""),r.get("Card Number",""),
                        r.get("Variance",""),"English",r.get("Card Condition","Near Mint"),f"{value:.2f}",
                        "HoloDex export",r.get("Date Added",""),"","Imported; verify exact variant"])
    print(out)
if __name__=="__main__": main()
