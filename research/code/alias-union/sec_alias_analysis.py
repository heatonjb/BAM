"""Alias-union coverage ladder and coverage-inclusive tax, SEC CY2023 (v2).

Regime P  = preferred tag only (chain[0]).
Regime S  = P + strict synonyms (same construct, different standard tag).
Regime B  = S + broad tags that measure a DIFFERENT construct (SG&A for S&M,
            payables+accrued for payables, bank income lines for revenue).
Regime U  = full union (= B).
"""
import json, statistics as st, collections, math

IDX = json.load(open("/tmp/opencode/frames_index.json"))
def V(metric, tag): return IDX[f"{metric}|{tag}"]["vals"]

MAP = {
 "revenue": {
   "pref": ["RevenueFromContractWithCustomerExcludingAssessedTax"],
   "syn":  ["RevenueFromContractWithCustomerIncludingAssessedTax",
            "Revenues","SalesRevenueNet","SalesRevenueGoodsNet",
            "SalesRevenueServicesNet"],
   "broad":["RevenuesNetOfInterestExpense","RegulatedAndUnregulatedOperatingRevenue",
            "InterestAndDividendIncomeOperating","NoninterestIncome",
            "RevenuesExcludingInterestAndDividends"],
 },
 "cogs": {
   "pref": ["CostOfGoodsAndServicesSold"],
   "syn":  ["CostOfRevenue","CostOfGoodsSold","CostOfServices","CostOfSales"],
   "broad":[],
 },
 "gross": {"pref": ["GrossProfit"], "syn": [], "broad": []},
 "sm": {
   "pref": ["SellingAndMarketingExpense"],
   "syn":  ["MarketingExpense","SellingExpense"],
   "broad":["SellingGeneralAndAdministrativeExpense","GeneralAndAdministrativeExpense"],
 },
 "ar": {
   "pref": ["AccountsReceivableNetCurrent"],
   "syn":  ["ReceivablesNetCurrent","AccountsReceivableGrossCurrent",
            "AccountsAndOtherReceivablesNetCurrent","AccountsReceivableNet",
            "AccountsReceivableGross"],
   "broad":[],
 },
 "inv": {
   "pref": ["InventoryNet"],
   "syn":  ["InventoryFinishedGoodsNetOfReserves","InventoryGross",
            "InventoryFinishedGoods","InventoryRawMaterialsAndSupplies",
            "InventoryWorkInProcessNetOfReserves"],
   "broad":[],
 },
 "ap": {
   "pref": ["AccountsPayableCurrent"],
   "syn":  ["AccountsPayableTradeCurrent"],
   "broad":["AccountsPayableAndAccruedLiabilitiesCurrent",
            "AccountsPayableCurrentAndNoncurrent",
            "AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent"],
 },
}

def order(metric, regime):
    m = MAP[metric]
    if regime == "P": return m["pref"]
    if regime == "S": return m["pref"]+m["syn"]
    return m["pref"]+m["syn"]+m["broad"]

def resolve(metric, regime):
    o = order(metric, regime)
    present = set()
    for t in o: present |= set(V(metric, t))
    out = {}
    for c in present:
        for t in o:
            if V(metric, t).get(c) is not None:
                out[c] = V(metric, t)[c]; break
    return out

def resolve_custom(metric, tags):
    present = set()
    for t in tags: present |= set(V(metric, t))
    out = {}
    for c in present:
        for t in tags:
            if V(metric, t).get(c) is not None:
                out[c] = V(metric, t)[c]; break
    return out

def pctile(v, pop):
    pop = sorted(pop); return 100.0*sum(x < v for x in pop)/len(pop)
def dec(p): return min(9, int(p//10))

def tax(popP, popU):
    common = set(popP) & set(popU)
    d = [abs(pctile(popU[c], popU.values())-pctile(popP[c], popP.values())) for c in common]
    churn = sum(dec(pctile(popP[c],popP.values())) != dec(pctile(popU[c],popU.values()))
                for c in common)
    q = st.quantiles(popP.values(), n=4) if len(popP) > 3 else [0,0,1]
    return {"n_common": len(common),
            "taxDec": churn/len(common) if common else float("nan"),
            "dMean": st.mean(d) if d else float("nan"),
            "dMed": st.median(d) if d else float("nan"),
            "taxMed": abs(st.median(popU.values())-st.median(popP.values()))/(q[2]-q[0] or 1)}

def ratio(num, den):
    return {c: num[c]/den[c] for c in set(num)&set(den) if den.get(c)}

R = {}
for m in MAP:
    R[m] = {rr: resolve(m, rr) for rr in ("P","S","U")}

univ = set(V("universe","Assets")) | set(V("universe","NetIncomeLoss"))

def gross_margin(regime):
    rev = R["revenue"][regime]
    cogs = R["cogs"][regime]
    gp = dict(R["gross"]["U"])                     # reported GrossProfit (regime-independent)
    for c in set(rev)&set(cogs): gp.setdefault(c, rev[c]-cogs[c])
    return {c: gp[c]/rev[c] for c in set(gp)&set(rev) if rev[c] and gp[c] is not None}

metrics = {
 "Revenue":        {r:R["revenue"][r] for r in "PSU"},
 "COGS":           {r:R["cogs"][r] for r in "PSU"},
 "Gross margin":   {r:gross_margin(r) for r in "PSU"},
 "S&M intensity":  {r:ratio(R["sm"][r], R["revenue"][r]) for r in "PSU"},
 "DSO":            {r:{c:R["ar"][r][c]/R["revenue"][r][c]*365
                       for c in set(R["ar"][r])&set(R["revenue"][r]) if R["revenue"][r][c]} for r in "PSU"},
 "DIO":            {r:{c:R["inv"][r][c]/R["cogs"][r][c]*365
                       for c in set(R["inv"][r])&set(R["cogs"][r]) if R["cogs"][r][c]} for r in "PSU"},
 "DPO":            {r:{c:R["ap"][r][c]/R["cogs"][r][c]*365
                       for c in set(R["ap"][r])&set(R["cogs"][r]) if R["cogs"][r][c]} for r in "PSU"},
}

print(f"universe (Assets ∪ NetIncomeLoss) n = {len(univ)}\n")
hdr=(f"{'metric':15s}{'nP':>6s}{'nS':>6s}{'nU':>6s}{'covLossP':>9s}"
     f"{'recSyn%':>8s}{'recBroad%':>10s}{'taxDecP-U':>10s}{'taxDecS-U':>10s}"
     f"{'dMean':>7s}{'dMed':>7s}{'direct%':>8s}{'covU/univ':>10s}")
print(hdr); print("-"*len(hdr))
res={}
for name,reg in metrics.items():
    P,S,U=reg["P"],reg["S"],reg["U"]
    nP,nS,nU=len(P),len(S),len(U)
    covLossP=1-nP/nU
    recSyn=(nS-nP)/(nU-nP) if nU>nP else float('nan')
    recBroad=(nU-nS)/(nU-nP) if nU>nP else float('nan')
    tPU=tax(P,U); tSU=tax(S,U); tPS=tax(P,S)
    res[name]=dict(nP=nP,nS=nS,nU=nU,covLossP=covLossP,recSyn=recSyn,recBroad=recBroad,
                   taxDecPU=tPU["taxDec"],taxDecSU=tSU["taxDec"],taxDecPS=tPS["taxDec"],
                   dMean=tPU["dMean"],dMed=tPU["dMed"],taxMed=tPU["taxMed"],
                   directShare=nP/nU,cov_univ=nU/len(univ))
    print(f"{name:15s}{nP:6d}{nS:6d}{nU:6d}{covLossP:9.3f}{recSyn*100:8.1f}{recBroad*100:10.1f}"
          f"{tPU['taxDec']:10.3f}{tSU['taxDec']:10.3f}{tPU['dMean']:7.2f}{tPU['dMed']:7.2f}"
          f"{nP/nU:8.3f}{nU/len(univ):10.3f}")

print("\n=== validate against prior run: revenue 4-tag union (pref+Including+Revenues+NetInt) ===")
u4 = resolve_custom("revenue",["RevenueFromContractWithCustomerExcludingAssessedTax",
       "RevenueFromContractWithCustomerIncludingAssessedTax","Revenues",
       "RevenuesNetOfInterestExpense"])
p1 = R["revenue"]["P"]
t=tax(p1,u4)
print(f"nP={len(p1)} nU4={len(u4)} covLoss={1-len(p1)/len(u4):.3f} taxDec={t['taxDec']:.3f} dMean={t['dMean']:.2f}")

print("\n=== answering-tag distribution (full union, first-present-wins) ===")
for m in MAP:
    o=order(m,"U"); present=set()
    for t in o: present|=set(V(m,t))
    a=collections.Counter()
    for c in present:
        for t in o:
            if V(m,t).get(c) is not None: a[t]+=1; break
    tot=sum(a.values())
    print(f"{m:8s} n={tot:5d} pref={a[MAP[m]['pref'][0]]/tot:.3f} :: "+
          " · ".join(f"{t[:30]}={n}" for t,n in a.most_common()))

json.dump({"metrics":res,"universe":len(univ)},open("/tmp/opencode/sec_result.json","w"),indent=1,default=str)
print("\nwrote /tmp/opencode/sec_result.json")
