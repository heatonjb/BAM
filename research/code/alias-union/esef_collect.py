"""Collect a cross-country ESEF/UKSEF filing sample from the XBRL International
open-filings API (filings.xbrl.org) and cache the XBRL-JSON (OIM) packages.

Polite: modest concurrency, caching, retry. Only filings with a processed
JSON are kept.
"""
import json, os, time, sys, collections
import requests
from concurrent.futures import ThreadPoolExecutor

CACHE = "/root/code/personal/research/business-as-machine/research/code/alias-union/cache/esef"
os.makedirs(CACHE, exist_ok=True)
S = requests.Session()
S.headers.update({"User-Agent": "business-as-machine research contact@example.com",
                  "Accept": "application/json"})
API = "https://filings.xbrl.org/api/filings"

COUNTRIES = ["FR","SE","IT","NL","DK","FI","NO","BE","AT","PL","ES","PT","LU","GR","CY","GB"]
PER_COUNTRY = 40

def list_country(cc):
    out=[]
    page=1
    while len(out) < PER_COUNTRY * 3 and page <= 6:
        u=f"{API}?filter%5Bcountry%5D={cc}&page%5Bsize%5D=200&page%5Bnumber%5D={page}"
        try: d=S.get(u,timeout=40).json()
        except Exception: break
        data=d.get("data",[])
        if not data: break
        for x in data:
            a=x["attributes"]
            if a.get("json_url"):
                out.append({"country":cc,"period_end":a.get("period_end"),
                            "json_url":a["json_url"],
                            "entity":x.get("relationships",{}).get("entity",{})})
        page+=1
    return out

def fetch(item):
    url="https://filings.xbrl.org"+item["json_url"]
    fn=os.path.join(CACHE, item["json_url"].strip("/").replace("/","__"))
    if os.path.exists(fn) and os.path.getsize(fn)>1000:
        return ("cached", item, fn)
    for a in range(3):
        try:
            r=S.get(url,timeout=90)
            if r.status_code==200 and r.content[:1]==b"{":
                with open(fn,"wb") as f: f.write(r.content)
                return ("ok", item, fn)
            time.sleep(1+a)
        except Exception:
            time.sleep(2*(a+1))
    return ("fail", item, None)

def main():
    idx=[]
    for cc in COUNTRIES:
        items=list_country(cc)
        # prefer 2022/2023 period ends, then any
        pref=[i for i in items if (i["period_end"] or "")[:4] in ("2022","2023")]
        sel=(pref or items)[:PER_COUNTRY]
        idx.extend(sel)
        print(cc, "available", len(items), "selected", len(sel))
    json.dump(idx, open(os.path.join(CACHE,"_index.json"),"w"))
    print("total to fetch", len(idx))
    results=[]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i,r in enumerate(ex.map(fetch, idx)):
            results.append(r)
            if (i+1)%50==0: print("fetched", i+1, flush=True)
    ok=sum(1 for r in results if r[0]=="ok"); ca=sum(1 for r in results if r[0]=="cached")
    fa=sum(1 for r in results if r[0]=="fail")
    print(f"ok={ok} cached={ca} fail={fa}")
    json.dump([r[1]|{"file":r[2]} for r in results if r[2]],
              open(os.path.join(CACHE,"_downloaded.json"),"w"))

if __name__=="__main__":
    main()
