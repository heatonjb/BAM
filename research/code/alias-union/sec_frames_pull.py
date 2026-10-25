"""Pull SEC XBRL Frames for the extended alias-union mapping (CY2023).

Declares a descriptive User-Agent and throttles below the SEC 10 req/s ceiling.
Caches every frame to disk so the coverage/tax computation is re-runnable
without re-querying.
"""
import json, os, time, sys
import requests

HDR = {"User-Agent": "business-as-machine research contact@example.com"}
S = requests.Session(); S.headers.update(HDR)
CACHE = "/tmp/opencode/frames"
os.makedirs(CACHE, exist_ok=True)

# Extended tag mapping. (tag, period_kind, tier)
#   tier: 'P' preferred, 'S' strict synonym, 'B' broad/construct-shifting,
#         'U' universe anchor
CAND = {
 "revenue": [
   ("RevenueFromContractWithCustomerExcludingAssessedTax","P"),
   ("RevenueFromContractWithCustomerIncludingAssessedTax","P"),
   ("Revenues","S"),
   ("RevenuesNetOfInterestExpense","B"),
   ("RegulatedAndUnregulatedOperatingRevenue","B"),
   ("HealthCareOrganizationRevenue","B"),
   ("RealEstateRevenueNet","B"),
   ("SalesRevenueNet","S"),
   ("SalesRevenueGoodsNet","S"),
   ("SalesRevenueServicesNet","S"),
   ("InterestAndDividendIncomeOperating","B"),
   ("NoninterestIncome","B"),
   ("RevenuesExcludingInterestAndDividends","B"),
 ],
 "cogs": [
   ("CostOfGoodsAndServicesSold","P"),
   ("CostOfRevenue","P"),
   ("CostOfGoodsSold","S"),
   ("CostOfServices","S"),
   ("CostOfSales","S"),
 ],
 "gross": [
   ("GrossProfit","P"),
 ],
 "sm": [
   ("SellingAndMarketingExpense","P"),
   ("MarketingExpense","S"),
   ("SellingExpense","S"),
   ("SellingGeneralAndAdministrativeExpense","B"),
   ("GeneralAndAdministrativeExpense","B"),
 ],
 "ar": [
   ("AccountsReceivableNetCurrent","P"),
   ("ReceivablesNetCurrent","S"),
   ("AccountsReceivableGrossCurrent","S"),
   ("AccountsAndOtherReceivablesNetCurrent","S"),
   ("AccountsReceivableNet","S"),
   ("AccountsReceivableGross","S"),
 ],
 "inv": [
   ("InventoryNet","P"),
   ("InventoryFinishedGoodsNetOfReserves","S"),
   ("InventoryGross","S"),
   ("InventoryFinishedGoods","S"),
   ("InventoryRawMaterialsAndSupplies","S"),
   ("InventoryWorkInProcessNetOfReserves","S"),
 ],
 "ap": [
   ("AccountsPayableCurrent","P"),
   ("AccountsPayableTradeCurrent","S"),
   ("AccountsPayableAndAccruedLiabilitiesCurrent","B"),
   ("AccountsPayableCurrentAndNoncurrent","B"),
   ("AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent","B"),
 ],
 "universe": [
   ("Assets","U"),          # instantaneous
   ("NetIncomeLoss","U"),   # duration
 ],
}

def fetch(tag, period):
    fp = os.path.join(CACHE, f"{tag}__{period}.json")
    if os.path.exists(fp):
        with open(fp) as f: return json.load(f)
    u = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json"
    for attempt in range(4):
        try:
            r = S.get(u, timeout=45)
            if r.status_code == 404:
                data = {"data": []}
            else:
                r.raise_for_status(); data = r.json()
            with open(fp, "w") as f: json.dump(data, f)
            time.sleep(0.16)          # ~6 req/s, below 10/s ceiling
            return data
        except Exception as e:
            time.sleep(1.5 * (attempt + 1))
    print("FAIL", tag, period, file=sys.stderr)
    return {"data": []}

def main():
    INSTANT = {"ar", "inv", "ap"}
    rows = {}
    for metric, tags in CAND.items():
        for tag, tier in tags:
            if metric in INSTANT or (metric == "universe" and tag == "Assets"):
                period = "CY2023Q4I"
            else:
                period = "CY2023"
            d = fetch(tag, period)
            vals = {str(x["cik"]): x["val"] for x in d.get("data", []) if x.get("val") is not None}
            rows[f"{metric}|{tag}"] = {"tier": tier, "period": period, "n": len(vals),
                                        "vals": vals}
            print(f"{metric:8s} {tag:60s} tier={tier} n={len(vals)}")
    with open("/tmp/opencode/frames_index.json", "w") as f:
        json.dump(rows, f)
    print("total tag records:", len(rows))

if __name__ == "__main__":
    main()
