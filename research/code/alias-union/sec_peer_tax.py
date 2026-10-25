"""Peer-matched (2-digit SIC) coverage-inclusive tax and effective sample size.

Before = preferred-only regime P. After = strict-synonym regime S and full
union U. Reports within-cell tax_decile and how many industry cells clear the
n_eff floor (>=20 firms and preferred/synonym share >= 0.5) before vs after.
"""
import json, statistics as st, collections

IDX = json.load(open("/tmp/opencode/frames_index.json"))
SIC = json.load(open("/root/code/personal/research/business-as-machine/research/code/alias-union/cache/sic_map.json"))
SIC = {int(k): int(v) for k, v in SIC.items()}
def V(m,t): return IDX[f"{m}|{t}"]["vals"]

MAP = {
 "revenue":{"pref":["RevenueFromContractWithCustomerExcludingAssessedTax"],
   "syn":["RevenueFromContractWithCustomerIncludingAssessedTax","Revenues",
          "SalesRevenueNet","SalesRevenueGoodsNet","SalesRevenueServicesNet"],
   "broad":["RevenuesNetOfInterestExpense","RegulatedAndUnregulatedOperatingRevenue",
            "InterestAndDividendIncomeOperating","NoninterestIncome",
            "RevenuesExcludingInterestAndDividends"]},
 "cogs":{"pref":["CostOfGoodsAndServicesSold"],
   "syn":["CostOfRevenue","CostOfGoodsSold","CostOfServices","CostOfSales"],"broad":[]},
 "gross":{"pref":["GrossProfit"],"syn":[],"broad":[]},
 "sm":{"pref":["SellingAndMarketingExpense"],"syn":["MarketingExpense","SellingExpense"],
   "broad":["SellingGeneralAndAdministrativeExpense","GeneralAndAdministrativeExpense"]},
 "ar":{"pref":["AccountsReceivableNetCurrent"],
   "syn":["ReceivablesNetCurrent","AccountsReceivableGrossCurrent",
          "AccountsAndOtherReceivablesNetCurrent","AccountsReceivableNet",
          "AccountsReceivableGross"],"broad":[]},
 "inv":{"pref":["InventoryNet"],
   "syn":["InventoryFinishedGoodsNetOfReserves","InventoryGross","InventoryFinishedGoods",
          "InventoryRawMaterialsAndSupplies","InventoryWorkInProcessNetOfReserves"],"broad":[]},
 "ap":{"pref":["AccountsPayableCurrent"],"syn":["AccountsPayableTradeCurrent"],
   "broad":["AccountsPayableAndAccruedLiabilitiesCurrent",
            "AccountsPayableCurrentAndNoncurrent",
            "AccountsPayableAndAccruedLiabilitiesCurrentAndNoncurrent"]},
}
def order(m,r):
    x=MAP[m]
    return x["pref"] if r=="P" else (x["pref"]+x["syn"] if r=="S" else x["pref"]+x["syn"]+x["broad"])
def resolve(m,r):
    o=order(m,r); pres=set()
    for t in o: pres|=set(V(m,t))
    out={}
    for c in pres:
        for t in o:
            if V(m,t).get(c) is not None: out[c]=V(m,t)[c]; break
    return out

def pctile(v,pop):
    pop=sorted(pop); return 100.0*sum(x<v for x in pop)/len(pop)
def dec(p): return min(9,int(p//10))

R={m:{r:resolve(m,r) for r in "PSU"} for m in MAP}
univ=set(V("universe","Assets"))|set(V("universe","NetIncomeLoss"))

def cells(pop):
    d=collections.defaultdict(list)
    for c,v in pop.items():
        s=SIC.get(int(c))
        if s: d[s//100].append((c,v))
    return d

def cell_tax(popP,popU):
    cP=cells(popP); cU=cells(popU); churn=[]; dm=[]; cells_ok=0
    for s in set(cP)&set(cU):
        pp={c:v for c,v in cP[s]}; pu={c:v for c,v in cU[s]}
        common=set(pp)&set(pu)
        if len(common)<5: continue
        vp=list(pp.values()); vu=list(pu.values())
        n=0
        for c in common:
            if dec(pctile(pp[c],vp))!=dec(pctile(pu[c],vu)): n+=1
        churn.append(n/len(common))
    return st.mean(churn) if churn else float('nan')

# metric populations (ratios)
def ratio(a,b): return {c:a[c]/b[c] for c in set(a)&set(b) if b.get(c)}
metrics={}
metrics["Revenue"]={r:R["revenue"][r] for r in "PSU"}
metrics["COGS"]={r:R["cogs"][r] for r in "PSU"}
def gm(r):
    rev=R["revenue"][r]; cogs=R["cogs"][r]; gp=dict(R["gross"]["U"])
    for c in set(rev)&set(cogs): gp.setdefault(c,rev[c]-cogs[c])
    return {c:gp[c]/rev[c] for c in set(gp)&set(rev) if rev[c]}
metrics["Gross margin"]={r:gm(r) for r in "PSU"}
metrics["S&M intensity"]={r:ratio(R["sm"][r],R["revenue"][r]) for r in "PSU"}
metrics["DSO"]={r:{c:R["ar"][r][c]/R["revenue"][r][c]*365 for c in set(R["ar"][r])&set(R["revenue"][r]) if R["revenue"][r][c]} for r in "PSU"}
metrics["DIO"]={r:{c:R["inv"][r][c]/R["cogs"][r][c]*365 for c in set(R["inv"][r])&set(R["cogs"][r]) if R["cogs"][r][c]} for r in "PSU"}
metrics["DPO"]={r:{c:R["ap"][r][c]/R["cogs"][r][c]*365 for c in set(R["ap"][r])&set(R["cogs"][r]) if R["cogs"][r][c]} for r in "PSU"}

def cells_clearing(pop, floor=0.5, minsz=20):
    d=collections.defaultdict(int)
    for c in pop:
        s=SIC.get(int(c))
        if s: d[s//100]+=1
    # need cell universe size = U-population within cell later; here count per regime
    return d
def floor_status(reg):
    """cells with >=20 in U-population and regime share>=0.5."""
    ok=0; tot=0
    cP=cells(reg["P"]); cS=cells(reg["S"]); cU=cells(reg["U"])
    for s in cU:
        nc=sum(1 for c in reg["U"] if SIC.get(int(c),0)//100==s and nc is not None)
    return None

print(f"{'metric':15s}{'nP':>6s}{'nS':>6s}{'nU':>6s}{'taxDecPU_2d':>12s}{'taxDecSU_2d':>12s}")
res={}
for name,reg in metrics.items():
    tp=cell_tax(reg["P"],reg["U"]); ts=cell_tax(reg["S"],reg["U"])
    nP,nS,nU=len(reg["P"]),len(reg["S"]),len(reg["U"])
    res[name]=dict(nP=nP,nS=nS,nU=nU,taxPU2d=tp,taxSU2d=ts)
    print(f"{name:15s}{nP:6d}{nS:6d}{nU:6d}{tp:12.3f}{ts:12.3f}")

# effective sample size: cells clearing the floor, before (P) vs after (S/U)
print("\n=== effective sample size by 2-digit SIC cell ===")
print(f"{'metric':15s}{'cells≥20':>9s}{'Pclear':>7s}{'Sclear':>7s}{'Uclear':>7s}{'Pshare':>7s}{'Sshare':>7s}")
for name,reg in metrics.items():
    cP=collections.Counter(); cS=collections.Counter(); cU=collections.Counter()
    for c in reg["P"]: s=SIC.get(int(c));  s and cP.__setitem__(s//100,cP[s//100]+1)
    for c in reg["S"]: s=SIC.get(int(c));  s and cS.__setitem__(s//100,cS[s//100]+1)
    for c in reg["U"]: s=SIC.get(int(c));  s and cU.__setitem__(s//100,cU[s//100]+1)
    big=[s for s in cU if cU[s]>=20]
    Pc=sum(1 for s in big if cP[s]>=20 and cP[s]/cU[s]>=0.5)
    Sc=sum(1 for s in big if cS[s]>=20 and cS[s]/cU[s]>=0.5)
    Uc=sum(1 for s in big if cU[s]>=20 and cU[s]>=20)  # union always covers
    print(f"{name:15s}{len(big):9d}{Pc:7d}{Sc:7d}{Uc:7d}{len(reg['P'])/len(reg['U']):7.3f}{len(reg['S'])/len(reg['U']):7.3f}")

json.dump(res,open("/tmp/opencode/sec_peer_result.json","w"),indent=1,default=str)
print("\nwrote /tmp/opencode/sec_peer_result.json")
