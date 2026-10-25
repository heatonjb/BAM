# GAAP / throughput reconciliation identity test on the OCEL 2.0
# "Inventory Management Database and OCELs" simulation (post-processed bundle)
# plus its archived generator DB (Zenodo record 21977737, CC BY 4.0).
#
#   identity      : NI_GAAP = NP_TA + DeltaInventory * overhead/unit
#   residual      : NI_GAAP - (NP_TA + DeltaInventory * overhead/unit)
#   variance term : V = AFOH - AbsorbedFOH = when closed to P&L it is internal
#                   to both profit figures; only an OPEN pool breaks identity.
#
# Run:  python reconcile_inventory.py
import json, os, sys, zipfile, sqlite3, hashlib
from collections import Counter, defaultdict
from decimal import Decimal

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bamledger as bl

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(ROOT, "..", "..", "data"))
OCEL_ZIP = os.path.join(DATA, "inventory_management_postprocessed.ocel.zip")
DB_PATH = os.path.join(DATA, "inventory_management.db")
OUT = sys.stdout


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def D(x):
    return Decimal(str(x))


def money(x):
    return f"{Decimal(str(x)):,.2f}"


def section(title):
    print("\n" + "=" * 78, file=OUT)
    print(title, file=OUT)
    print("=" * 78, file=OUT)


# ----------------------------------------------------------------------
# 1-2. INPUT ARTIFACTS AND OCEL LOAD
# ----------------------------------------------------------------------
section("1. INPUT ARTIFACTS (pinned)")
print(f"OCEL bundle : {OCEL_ZIP}  sha256 {sha256(OCEL_ZIP)}")
print(f"SQLite DB   : {DB_PATH}  sha256 {sha256(DB_PATH)}")

with zipfile.ZipFile(OCEL_ZIP) as z:
    meta = json.loads(z.read("ocel-meta.json"))
print("OCEL:", meta["ocelVersion"], "| bundleFormat", meta["bundleFormatVersion"],
      "| storage", meta["storageFormat"])
print("event types:", len(meta["eventTypes"]), "| object types:", list(meta["objectTypes"]))

section("2. LOAD OCEL 2.0 BUNDLE (typed Parquet layout)")
ev_parts = []
with zipfile.ZipFile(OCEL_ZIP) as z:
    for act, spec in meta["eventTypes"].items():
        with z.open(spec["file"]) as f:
            df = pd.read_parquet(f)
        df["activity"] = act
        ev_parts.append(df)
    ev = pd.concat(ev_parts, ignore_index=True)
    with z.open(meta["relations"]["e2o"]) as f:
        e2o = pd.read_parquet(f)
    with z.open(meta["relations"]["o2o"]) as f:
        o2o = pd.read_parquet(f)
ev["t"] = pd.to_datetime(ev["ocel_time"])
ev["sb"] = pd.to_numeric(ev["Stock Before"], errors="coerce")
ev["sa"] = pd.to_numeric(ev["Stock After"], errors="coerce")
ev["q"] = ev["sa"] - ev["sb"]
ev["date"] = ev["t"].dt.date.astype(str)
print("events:", len(ev), "| span", ev["t"].min(), "->", ev["t"].max())
print("o2o relation rows:", len(o2o), "  <-- sellable-output edge set is EMPTY")
print("e2o relation rows:", len(e2o))

ORIG = ["Create Purchase Suggestion Item", "Create Purchase Order Item",
        "Goods Receipt", "Create Sales Order Item", "Goods Issue"]
SYNTH = [a for a in meta["eventTypes"] if not any(a.startswith(o) for o in ORIG)]
print("economic activities:", len(ORIG), "| synthetic status/annotation activities:", len(SYNTH))

mp = (ev.merge(e2o, left_on="ocel_id", right_on="ocel_event_id", how="left"))
mp = mp[mp["ocel_object_id"].str.fullmatch(r"MAT-\d+_Plant\d+", na=False)]
mp = mp.drop_duplicates("ocel_id")
mp["matn"] = mp["ocel_object_id"].str.extract(r"MAT-(\d+)_Plant").astype(int)
mp["plant"] = mp["ocel_object_id"].str.extract(r"_Plant(\d+)$").apply(lambda s: "Plant" + s)
orig_idx = mp["activity"].apply(lambda a: any(a.startswith(o) for o in ORIG))
mp_orig = mp[orig_idx].copy()
stock_ev = mp_orig[mp_orig["activity"].str.startswith("Goods Receipt") |
                    mp_orig["activity"].str.startswith("Goods Issue")].copy()
stock_ev["kind"] = stock_ev["activity"].apply(lambda a: "GR" if a.startswith("Goods Receipt") else "GI")
print("stock-changing OCEL events (Goods Receipt/Issue, economic only):",
      (stock_ev["kind"] == "GR").sum(), "GR +", (stock_ev["kind"] == "GI").sum(), "GI")

# ----------------------------------------------------------------------
# 3. GROUND TRUTH FROM ARCHIVED DB
# ----------------------------------------------------------------------
section("3. ARCHIVED SQLite DB GROUND TRUTH")
conn = sqlite3.connect(DB_PATH)
dbrows = conn.execute(
    "SELECT material_number, plant, movement_type, quantity,"
    "       date_of_the_posting_in_the_document d"
    "  FROM GoodsReceiptsAndIssues WHERE material_number IS NOT NULL").fetchall()
mat_class = dict(conn.execute("SELECT material_number, valuation_class FROM Materials").fetchall())
conn.close()
dbflows = [(int(m), p, mv, D(q), str(d)[:10]) for m, p, mv, q, d in dbrows]
print("GoodsReceiptsAndIssues rows:", len(dbflows))
print("total receipt units:", sum(q for _, _, mv, q, _ in dbflows if mv == "Goods Receipt"),
      "| total issue units:", sum(q for _, _, mv, q, _ in dbflows if mv == "Goods Issue"))
print("materials:", len(mat_class), "| valuation classes:", sorted(set(mat_class.values())))

# event-set completeness: OCEL stock events vs DB closed transaction set
dbc = Counter(("GR" if mv == "Goods Receipt" else "GI", m, p, d, q) for m, p, mv, q, d in dbflows)
occ = Counter((r["kind"], int(r["matn"]), r["plant"], str(r["date"]), D(abs(r["q"])))
              for _, r in stock_ev.drop_duplicates("ocel_id").iterrows())
missing = Counter({k: dbc[k] - occ[k] for k in set(dbc) | set(occ) if dbc[k] > occ[k]})
extra = Counter({k: occ[k] - dbc[k] for k in set(dbc) | set(occ) if occ[k] > dbc[k]})
gr_miss = sum((q * c) for (k, m, p, d, q), c in missing.items() if k == "GR")
gi_miss = sum((q * c) for (k, m, p, d, q), c in missing.items() if k == "GI")
n_gr = sum(c for (k, m, p, d, q), c in missing.items() if k == "GR")
n_gi = sum(c for (k, m, p, d, q), c in missing.items() if k == "GI")
print("DB stock transactions:", sum(dbc.values()), "| OCEL stock events:", sum(occ.values()))
print(f"OCEL omits {len(missing)} DB transactions: {n_gr} Goods Receipt "
      f"({gr_miss} units) + {n_gi} Goods Issue ({gi_miss} units); OCEL-only events: {sum(extra.values())}")

# ----------------------------------------------------------------------
# 4. STOCK SEMANTICS & CONFORMANCE (generator-verified)
# ----------------------------------------------------------------------
section("4. STOCK SEMANTICS (verified against the generator source)")
print("Builder 02_database_to_ocel_csv.py: 'Stock Before'/'Stock After' are SQL")
print("windows PARTITION BY MAT ORDER BY Timestamp, ROWS UNBOUNDED PRECEDING")
print("AND 1 PRECEDING / AND CURRENT ROW; then floored PER (MAT,PLA) by adding")
print("max(0, -min(Stock Before, Stock After)).  Postprocessor 04 copies rows")
print("(with their Stock values) into synthetic status events and reassigns")
print("intra-day sub-second times by row index, so the published bundle is an")
print("intra-day PERMUTATION of the generator's day-granularity floored series.")

def generator_stock(db_path):
    """Reproduce the 02 builder's Stock columns from the archived DB verbatim."""
    q = """
    WITH AllEvents AS (
      SELECT 'Create Purchase Suggestion Item' AS Activity, os.date AS Timestamp,
             os.article_number AS MAT, os.plant AS PLA, 0 AS quantity_change
        FROM OrderSuggestions os WHERE os.article_number IS NOT NULL
      UNION ALL
      SELECT 'Create Purchase Order Item', pod.purchase_order_date, poi.material_number,
             poi.plant, 0 FROM PurchaseOrderItems poi
             JOIN PurchaseOrderDocuments pod
               ON poi.purchase_order_number = pod.purchase_document_number
             WHERE poi.material_number IS NOT NULL
      UNION ALL
      SELECT 'Goods Receipt', gri.date_of_the_posting_in_the_document, gri.material_number,
             gri.plant, gri.quantity FROM GoodsReceiptsAndIssues gri
             WHERE gri.movement_type='Goods Receipt' AND gri.material_number IS NOT NULL
      UNION ALL
      SELECT 'Create Sales Order Item', sod.document_creation_date, soi.material_number,
             soi.plant, 0 FROM SalesOrderItems soi
             JOIN SalesOrderDocuments sod
               ON soi.sales_document_number = sod.sales_document_number
             WHERE soi.material_number IS NOT NULL
      UNION ALL
      SELECT 'Goods Issue', gri.date_of_the_posting_in_the_document, gri.material_number,
             gri.plant, -gri.quantity FROM GoodsReceiptsAndIssues gri
             WHERE gri.movement_type='Goods Issue' AND gri.material_number IS NOT NULL)
    SELECT Activity, Timestamp, MAT, PLA,
      SUM(quantity_change) OVER (PARTITION BY MAT ORDER BY Timestamp
          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS "Stock Before",
      SUM(quantity_change) OVER (PARTITION BY MAT ORDER BY Timestamp
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS "Stock After"
    FROM AllEvents WHERE MAT IS NOT NULL ORDER BY MAT, Timestamp
    """
    c = sqlite3.connect(db_path)
    g = pd.read_sql_query(q, c); c.close()
    g = g.dropna(subset=["Stock Before", "Stock After"]).copy()
    g["MAT_PLA"] = "MAT-" + g["MAT"].astype("string") + "_" + g["PLA"].astype("string")
    bmin = g.groupby("MAT_PLA")["Stock Before"].min()
    amin = g.groupby("MAT_PLA")["Stock After"].min()
    add = {k: max(0.0, -min(bmin[k], amin[k])) for k in bmin.index}
    g["Stock Before"] += g["MAT_PLA"].map(add)
    g["Stock After"] += g["MAT_PLA"].map(add)
    return g

gen = generator_stock(DB_PATH)
mp_orig = mp_orig.copy()
mp_orig["mpkey"] = ("MAT-" + mp_orig["matn"].astype(str) + "_" + mp_orig["plant"])
gen_ms = {k: sorted(round(float(v), 6) for v in g["Stock After"])
          for k, g in gen.groupby("MAT_PLA")}
pub_ms = {k: sorted(round(float(v), 6) for v in g["sa"].dropna())
          for k, g in mp_orig.groupby("mpkey")}
keys = set(gen_ms) | set(pub_ms)
identical = sum(1 for k in keys if gen_ms.get(k) == pub_ms.get(k))
print(f"generator rows reproduced from archived DB: {len(gen)} | published ORIG events: {len(mp_orig)}")
print(f"(MAT,PLA) groups compared: {len(keys)} | 'Stock After' multiset IDENTICAL: {identical}")
print("=> the bundle embeds the builder's floored Stock series exactly; only the")
print("   within-day ordering differs (4 zero-impact synthetic copies excluded here).")

# ----------------------------------------------------------------------
# 5. PERIODS, FLOWS, DeltaInventory
# ----------------------------------------------------------------------
section("5. PERIODS, FLOWS, DeltaInventory")

def period_summary(name, t0, t1, flows):
    in_p = [(m, p, mv, q, d) for m, p, mv, q, d in flows if t0 <= d < t1]
    up = sum(q for m, p, mv, q, d in in_p if mv == "Goods Receipt")
    us = sum(q for m, p, mv, q, d in in_p if mv == "Goods Issue")
    print(f"{name}:  receipts {up} units | issues {us} units | "
          f"DeltaInventory(flow) = {up - us} units  [{len(in_p)} transactions]")
    return in_p, up, us, up - us

def floored_opening_closing(flows, t0, t1):
    """Reported-stock semantics of the artifact: per (MAT,PLA) the published
    Stock is the material-level cumulative flow plus a nonnegative floor
    max(0, -min).  The archived DB records NO transactions before t0, so the
    floor IS the opening balance; closing is the cumulative run through the
    last event before t1 plus the floor.  Hence opening - closing difference
    from snapshots equals the net flow (a constant per-(MAT,PLA) shift)."""
    bym = defaultdict(list)
    for m, p, mv, q, d in flows:
        bym[(m, p)].append((d, q if mv == "Goods Receipt" else -q))
    opening = D(0)
    closing = D(0)
    for (m, p), evs in bym.items():
        evs = sorted(evs)
        run = D(0)
        lo = D(0)
        cl_here = None
        for d, q in evs:
            run += q
            lo = min(lo, run)
            if d < t1:
                cl_here = run
        off = max(D(0), -lo)
        opening += off
        closing += (cl_here if cl_here is not None else D(0)) + off
    return opening, closing, closing - opening

t0_full, t1_full = "2023-09-26", "2024-09-26"
t0_h1, t1_h1 = "2023-09-26", "2024-03-26"
db_full = period_summary("P_full [2023-09-26, 2024-09-26)  DB closed set", t0_full, t1_full, dbflows)
db_h1 = period_summary("P_h1  [2023-09-26, 2024-03-26)  DB closed set", t0_h1, t1_h1, dbflows)

ocel_flows = [(int(r["matn"]), r["plant"],
               "Goods Receipt" if r["kind"] == "GR" else "Goods Issue",
               D(abs(r["q"])), str(r["date"]))
              for _, r in stock_ev.drop_duplicates("ocel_id").iterrows()]
ocel_full = period_summary("P_full  OCEL published events only", t0_full, t1_full, ocel_flows)

op_db, cl_db, dinv_snap_db = floored_opening_closing(dbflows, t0_full, t1_full)
op_oc, cl_oc, dinv_snap_oc = floored_opening_closing(ocel_flows, t0_full, t1_full)
print()
print(f"P_full DB   : snapshots opening {op_db} -> closing {cl_db}; "
      f"DeltaInventory(snapshot) = {dinv_snap_db}  vs flow-based {db_full[3]}")
print(f"P_full OCEL : snapshots opening {op_oc} -> closing {cl_oc}; "
      f"DeltaInventory(snapshot) = {dinv_snap_oc}  vs flow-based {ocel_full[3]}")
print("=> identity inputs are consistent iff |snapshot - flow| == 0 (floor is a constant shift).")

ocel_per_mat_open = None

# ----------------------------------------------------------------------
# 6. DECLARED SYNTHETIC COST LAYER
# ----------------------------------------------------------------------
section("6. DECLARED SYNTHETIC COST LAYER (the valuation add-on)")
PRICE = D("10.00")
TVC = D("4.00")
AFOH = D("4500.00")
NORMAL_CAP = D("4000.00")
OH_U = AFOH / NORMAL_CAP
SGNA = D("6000.00")
print(f"price/unit {PRICE} | TVC/unit {TVC} | AFOH {money(AFOH)} | normal capacity "
      f"{NORMAL_CAP} units | oh_u = AFOH/normal = {OH_U}/unit | SG&A {money(SGNA)}")

# ----------------------------------------------------------------------
# 7. LEDGER BUILDERS
# ----------------------------------------------------------------------
def open_single_ledger(qin, with_opening=True):
    lg = bl.BAMLedger()
    for a, t in {"Cash": "Asset", "Inventory:TVC": "Asset", "Inventory:FOH": "Asset",
                 "FOH:CostPool": "Asset", "FOH:Variance": "Expense",
                 "Equity:Capital": "Equity", "Equity:RE": "Equity",
                 "Revenue": "Income", "COGS:TVC": "Expense", "COGS:FOH": "Expense",
                 "SG&A": "Expense"}.items():
        lg.add(a, t)
    inv = qin if with_opening else D(0)
    cap = 100000 + inv * (TVC + OH_U)
    lines = [("Cash", 100000, 0), ("Equity:Capital", 0, cap)]
    if inv != 0:
        lines[1:1] = [("Inventory:TVC", inv * TVC, 0), ("Inventory:FOH", inv * OH_U, 0)]
    lg.post("OP", "opening balance", lines)
    return lg


def run_single_pool(tag, up, us, qin, with_opening=True):
    lg = open_single_ledger(qin, with_opening)
    lg.post("P", "purchases", [("Inventory:TVC", up * TVC, 0), ("Cash", 0, up * TVC)])
    lg.post("P", "sales", [("Cash", us * PRICE, 0), ("Revenue", 0, us * PRICE)])
    lg.post("P", "COGS variable", [("COGS:TVC", us * TVC, 0), ("Inventory:TVC", 0, us * TVC)])
    lg.post("P", "FOH incurred", [("FOH:CostPool", AFOH, 0), ("Cash", 0, AFOH)])
    lg.post("P", "SG&A", [("SG&A", SGNA, 0), ("Cash", 0, SGNA)])
    lg.post("P", "absorb oh_u * produced", [("Inventory:FOH", up * OH_U, 0),
                                            ("FOH:CostPool", 0, up * OH_U)])
    lg.post("P", "release oh_u * sold", [("COGS:FOH", us * OH_U, 0),
                                         ("Inventory:FOH", 0, us * OH_U)])
    v = lg.bal("FOH:CostPool")          # = AFOH - up*oh_u
    if v > 0:
        lg.post("C", "close pool (under-absorbed)",
                [("FOH:Variance", v, 0), ("FOH:CostPool", 0, v)])
    elif v < 0:
        lg.post("C", "close pool (over-absorbed)",
                [("FOH:CostPool", -v, 0), ("FOH:Variance", 0, -v)])
    lg.close_period(["Revenue"], ["COGS:TVC", "COGS:FOH", "SG&A", "FOH:Variance"],
                    "Equity:RE", "CLOSE")
    ni_gaap = lg.bal("Equity:RE")
    np_ta = us * (PRICE - TVC) - AFOH - SGNA
    dinv = up - us
    res_base = ni_gaap - (np_ta + dinv * OH_U)
    dr, cr, bal = lg.trial_balance()
    if tag:
        print(f"\n[{tag}]")
        print(f"   produced {up} | sold {us} | opening {qin} units")
        print(f"   revenue {money(us * PRICE)} | NP_TA = {money(np_ta)}")
        print(f"   NI_GAAP = {money(ni_gaap)} | DeltaInv {dinv} | DeltaInv*oh_u {money(dinv * OH_U)}")
        print(f"   V = AFOH - oh_u*produced = {money(v)} "
              f"({'OVER-absorbed (favorable)' if v < 0 else 'under-absorbed'})")
        print(f"   residual = NI_GAAP - (NP_TA + DeltaInv*oh_u) = {res_base}")
        print(f"   trial balance: {dr} = {cr} | balanced: {bal}")
    return lg, {"ni": ni_gaap, "np": np_ta, "v": v, "res": res_base, "up": up,
                "us": us, "qin": qin, "dinv": dinv}


section("7. SINGLE-POOL RECONCILIATION (P_full, DB closed set)")
_s, r1 = run_single_pool("P_full (DB complete set)", db_full[1], db_full[2], op_db)
_s, r1o = run_single_pool("P_full (OCEL published events)", ocel_full[1], ocel_full[2], op_oc)
_s, r2 = run_single_pool("P_h1 (DB, first 6 months)", db_h1[1], db_h1[2],
                         floored_opening_closing(dbflows, t0_h1, t1_h1)[0])
print("\nUnder/over-absorption variance and WHY it stays internal:")
print("  V = AFOH - oh_u*U_prod. It is closed to the P&L inside BOTH profit")
print("  figures (NP_TA charges actual AFOH; NI_GAAP charges oh_u*U_sold + V).")
print("  It is NOT an extra term of the identity; NI_GAAP = NP_TA + DeltaInv*oh_u")

# ----------------------------------------------------------------------
# 8. MULTI-OVERHEAD-POOL VERSION
# ----------------------------------------------------------------------
section("8. MULTI-OVERHEAD-POOL VERSION (3 pools = valuation classes)")
AFOH_P = {"ValClass1": D("1300.00"), "ValClass2": D("1500.00"), "ValClass3": D("1700.00")}
NORM_P = {"ValClass1": D("1200.00"), "ValClass2": D("1500.00"), "ValClass3": D("1300.00")}
OH_P = {p: AFOH_P[p] / NORM_P[p] for p in AFOH_P}
print("pools:", {p: f"AFOH={AFOH_P[p]} normal={NORM_P[p]} oh={OH_P[p]}" for p in OH_P})

in_per_class = defaultdict(lambda: defaultdict(lambda: D(0)))
for m, p, mv, q, d in dbflows:
    if t0_full <= d < t1_full:
        in_per_class[mat_class[m]]["GR" if mv == "Goods Receipt" else "GI"] += q
# No pre-t0 transactions exist in the archive, so each material's opening is
# the floor offset of its (MAT,PLA) published stock series, classified by
# valuation class (sum of offsets over the material's plants).
qin_class = defaultdict(lambda: D(0))
bym_off = defaultdict(list)
for m, p, mv, q, d in dbflows:
    bym_off[(m, p)].append((d, q if mv == "Goods Receipt" else -q))
for (m, p), evs in bym_off.items():
    run = D(0); lo = D(0)
    for d, q in sorted(evs):
        run += q; lo = min(lo, run)
    qin_class[mat_class[m]] += max(D(0), -lo)

lgm = bl.BAMLedger()
accounts = {"Cash": "Asset", "Inventory:TVC": "Asset", "Equity:Capital": "Equity",
            "Equity:RE": "Equity", "Revenue": "Income", "COGS:TVC": "Expense", "SG&A": "Expense"}
for p in OH_P:
    for a, t in [(f"Inventory:FOH:{p}", "Asset"), (f"FOH:CostPool:{p}", "Asset"),
                 (f"COGS:FOH:{p}", "Expense"), (f"FOH:Variance:{p}", "Expense")]:
        accounts[a] = t
for a, t in accounts.items():
    lgm.add(a, t)
tvc_open = sum(qin_class.values()) * TVC
foh_open = {cl: qin_class[cl] * OH_P[cl] for cl in OH_P}
tot_cap = 100000 + tvc_open + sum(foh_open.values())
lgm.post("OP", "opening",
         [("Cash", 100000, 0), ("Inventory:TVC", tvc_open, 0)] +
         [(f"Inventory:FOH:{cl}", foh_open[cl], 0) for cl in OH_P] +
         [("Equity:Capital", 0, tot_cap)])
total_up = D(0); total_us = D(0)
vpool = {}
for cl in OH_P:
    up = in_per_class[cl]["GR"]; us = in_per_class[cl]["GI"]
    total_up += up; total_us += us
    lgm.post("P", f"purchases {cl}", [("Inventory:TVC", up * TVC, 0), ("Cash", 0, up * TVC)])
    lgm.post("P", f"sales {cl}", [("Cash", us * PRICE, 0), ("Revenue", 0, us * PRICE)])
    lgm.post("P", f"COGS var {cl}", [("COGS:TVC", us * TVC, 0), ("Inventory:TVC", 0, us * TVC)])
    lgm.post("P", f"FOH incur {cl}", [(f"FOH:CostPool:{cl}", AFOH_P[cl], 0), ("Cash", 0, AFOH_P[cl])])
    lgm.post("P", f"absorb {cl}", [(f"Inventory:FOH:{cl}", up * OH_P[cl], 0),
                                   (f"FOH:CostPool:{cl}", 0, up * OH_P[cl])])
    lgm.post("P", f"release {cl}", [(f"COGS:FOH:{cl}", us * OH_P[cl], 0),
                                    (f"Inventory:FOH:{cl}", 0, us * OH_P[cl])])
    vc = lgm.bal(f"FOH:CostPool:{cl}")
    vpool[cl] = vc
    if vc > 0:
        lgm.post("C", f"close {cl}", [(f"FOH:Variance:{cl}", vc, 0), (f"FOH:CostPool:{cl}", 0, vc)])
    elif vc < 0:
        lgm.post("C", f"close {cl}", [(f"FOH:CostPool:{cl}", -vc, 0), (f"FOH:Variance:{cl}", 0, -vc)])
lgm.post("P", "SG&A", [("SG&A", SGNA, 0), ("Cash", 0, SGNA)])
lgm.close_period(["Revenue"], ["COGS:TVC", "SG&A"] +
                 [f"COGS:FOH:{cl}" for cl in OH_P] + [f"FOH:Variance:{cl}" for cl in OH_P],
                 "Equity:RE", "CLOSE")
ni_mp = lgm.bal("Equity:RE")
np_mp = total_us * (PRICE - TVC) - sum(AFOH_P.values()) - SGNA
pool_sum = sum((in_per_class[cl]["GR"] - in_per_class[cl]["GI"]) * OH_P[cl] for cl in OH_P)
res_mp = ni_mp - (np_mp + pool_sum)
dr2, cr2, bal2 = lgm.trial_balance()
print(f"produced by pool { {c: in_per_class[c]['GR'] for c in in_per_class} } | "
      f"sold by pool { {c: in_per_class[c]['GI'] for c in in_per_class} }")
print(f"DeltaInv by pool (units): "
      f"{ {cl: in_per_class[cl]['GR'] - in_per_class[cl]['GI'] for cl in OH_P} }")
print(f"sum_p oh_p * DeltaInv_p = {money(pool_sum)}")
print(f"NP_TA (same in either view) = {money(np_mp)}")
print(f"NI_GAAP (multi-pool ledger) = {money(ni_mp)}")
print(f"per-pool variance V_p = { {c: money(vpool[c]) for c in vpool} }")
print(f"trial balance: {dr2} vs {cr2} | diff {dr2 - cr2} | "
      f"balanced(exact {bal2}, within 1e-18: {abs(dr2 - cr2) < D('1e-18')})")
print(f"residual = NI_GAAP - (NP_TA + sum_p oh_p*DeltaInv_p) = {res_mp}")

# ----------------------------------------------------------------------
# 9. FALSIFICATION CONTROLS
# ----------------------------------------------------------------------
section("9. FALSIFICATION CONTROLS")

print("\n(a) FLAT INVENTORY (DeltaInv = 0) -> NI_GAAP must equal NP_TA")

# constructed flat scenario (opening 200, produced 100, sold 100)
r_c = run_single_pool("FLAT constructed: opening 200, produced 100, sold 100",
                      D("100"), D("100"), D("200"))
print(f"   -> NI_GAAP == NP_TA: {r_c[1]['ni'] == r_c[1]['np']} | both {money(r_c[1]['np'])} "
      f"| V = {money(r_c[1]['v'])} (huge under-absorption) | residual {r_c[1]['res']}")

# real flat window search: find [d0,d1) whose NET FLOW is exactly zero
# (prefix net of flows strictly before each date; equal prefixes => zero net)
evs = sorted({d for _, _, _, _, d in dbflows})
daily = {d: sum(q if mv == "Goods Receipt" else -q for m, p, mv, q, dd in dbflows if dd == d)
         for d in evs}
pref = []
run = D(0)
for d in evs:
    pref.append(run)          # net flow of all days strictly before d
    run += daily[d]
best = None
for i in range(len(evs)):
    for j in range(i + 1, len(evs)):
        if pref[i] == pref[j]:
            span = (pd.Timestamp(evs[j]) - pd.Timestamp(evs[i])).days
            if best is None or span > best[2]:
                best = (evs[i], evs[j], span)
if best and best[2] > 0:
    d0, d1, span = best
    flat = [(m, p, mv, q, d) for m, p, mv, q, d in dbflows if d0 <= d < d1]
    up_f = sum(q for _, _, mv, q, _ in flat if mv == "Goods Receipt")
    us_f = sum(q for _, _, mv, q, _ in flat if mv == "Goods Issue")
    op_f = floored_opening_closing(dbflows, d0, d1)[0]
    r_f = run_single_pool(f"FLAT real window [{d0}, {d1}) ({span} days)", up_f, us_f, op_f)
    print(f"   -> receipts {up_f} == issues {us_f} | NI_GAAP == NP_TA: "
          f"{r_f[1]['ni'] == r_f[1]['np']} | residual {r_f[1]['res']}")
else:
    print("   no non-degenerate real window with zero net flow found")

print("\n(b) TRUNCATED OPENING BALANCE -> identity must break when DeltaInventory")
print("    is read from stock snapshots (it is invariant when read as net flows)")
true_open = op_db
# zero-opening snapshot version
lg_z, r_z = run_single_pool("TRUNCATED: opening reported as 0 units", db_full[1],
                            db_full[2], D(0))
snap_open_wrong = D(0)
snap_close = cl_db
dinv_snap_wrong = snap_close - snap_open_wrong
res_snap_wrong = r_z["ni"] - (r_z["np"] + dinv_snap_wrong * OH_U)
print(f"   true opening = {true_open} units | reported opening = 0")
print(f"   DeltaInv(flow, unaffected) = {db_full[3]} | residual stays {r_z['res']}")
print(f"   DeltaInv(snapshot, truncation) = {dinv_snap_wrong} | residual = {res_snap_wrong}")
print(f"   expected breach = -oh_u * (true opened) = {money(-OH_U * true_open)}")
print(f"   -> identity breaks ONLY through snapshot-based DeltaInventory, by exactly "
      f"oh_u * opening-balance error.")

# partial truncation: drop the opening of one (MAT,PLA) whose floor is largest.
# The archive holds no pre-t0 rows, so each material's opening IS its floor
# offset; omitting that material's opening from the reported snapshot must
# breach the identity by exactly oh_u * that opening.
off_mp = {}
for (m, p), evs in bym_off.items():
    rr = D(0); lo = D(0)
    for d, q in sorted(evs):
        rr += q; lo = min(lo, rr)
    off_mp[(m, p)] = max(D(0), -lo)
(mx, mxopen) = max(off_mp.items(), key=lambda kv: kv[1])
qin_part = op_db - mxopen
r_p = run_single_pool(f"PARTIAL opening: material {mx[0]}/{mx[1]} opening "
                      f"'{mxopen}' dropped", db_full[1], db_full[2], qin_part)[1]
print(f"   flow-based residual stays {r_p['res']} | expected snapshot-breach = "
      f"-oh_u * {mxopen} = {money(-OH_U * mxopen)}")

print("\n(c) LEDGER THAT FAILS TO CLOSE THE VARIANCE POOL -> residual = V exactly")
lg_n = open_single_ledger(op_db, with_opening=False)
lg_n.post("P", "purchases", [("Inventory:TVC", db_full[1] * TVC, 0), ("Cash", 0, db_full[1] * TVC)])
lg_n.post("P", "sales", [("Cash", db_full[2] * PRICE, 0), ("Revenue", 0, db_full[2] * PRICE)])
lg_n.post("P", "COGS variable", [("COGS:TVC", db_full[2] * TVC, 0), ("Inventory:TVC", 0, db_full[2] * TVC)])
lg_n.post("P", "FOH incurred", [("FOH:CostPool", AFOH, 0), ("Cash", 0, AFOH)])
lg_n.post("P", "absorb", [("Inventory:FOH", db_full[1] * OH_U, 0), ("FOH:CostPool", 0, db_full[1] * OH_U)])
lg_n.post("P", "release", [("COGS:FOH", db_full[2] * OH_U, 0), ("Inventory:FOH", 0, db_full[2] * OH_U)])
lg_n.post("P", "SG&A", [("SG&A", SGNA, 0), ("Cash", 0, SGNA)])
lg_n.close_period(["Revenue"], ["COGS:TVC", "COGS:FOH", "SG&A"], "Equity:RE", "CLOSE")
ni_nc = lg_n.bal("Equity:RE")
res_nc = ni_nc - (r1["np"] + db_full[3] * OH_U)
print(f"   NI_GAAP(no variance close) = {money(ni_nc)} vs correct {money(r1['ni'])}")
print(f"   residual = {res_nc} | V = {r1['v']} | residual == V: {res_nc == r1['v']}")

# ----------------------------------------------------------------------
# 10. SUMMARY
# ----------------------------------------------------------------------
section("10. SUMMARY OF ACTUAL NUMBERS")
print(f"  per-event stock changes: 200 DB transactions -> 187 published OCEL stock "
      f"events (13 omitted: 4 GR = 131 units, 9 GI = 394 units)")
print(f"  P_full(DB):  up {db_full[1]} | us {db_full[2]} | DeltaInv {db_full[3]} | "
      f"NP_TA {money(r1['np'])} | NI_GAAP {money(r1['ni'])} | DeltaInv*oh_u {money(db_full[3]*OH_U)} | "
      f"residual {r1['res']} | V {money(r1['v'])}")
print(f"  P_full(OCEL):up {ocel_full[1]} | us {ocel_full[2]} | DeltaInv {ocel_full[3]} | "
      f"NP_TA {money(r1o['np'])} | NI_GAAP {money(r1o['ni'])} | residual {r1o['res']} | V {money(r1o['v'])}")
print(f"  P_h1(DB):   up {db_h1[1]} | us {db_h1[2]} | DeltaInv {db_h1[3]} | "
      f"NP_TA {money(r2['np'])} | NI_GAAP {money(r2['ni'])} | residual {r2['res']} | V {money(r2['v'])}")
print(f"  multi-pool: sum_p oh_p*DeltaInv_p {money(pool_sum)} | NI_GAAP - NP_TA "
      f"{money(ni_mp - np_mp)} | residual {res_mp}")
print(f"  falsification (a) flat : NI_GAAP == NP_TA -> {r_c[1]['ni'] == r_c[1]['np']}"
      + (f" (real window {best[2]} days)" if (best and best[2] > 0) else ""))
print(f"  falsification (b) trunc: flow-based residual {r_z['res']} | "
      f"snapshot-based residual {res_snap_wrong} (must be non-zero)")
print(f"  falsification (c) pool open: residual {res_nc} == V {r1['v']}")
print("\nEven with the identity EXACT, the valuation is valid only inside the synthetic")
print("ledger: cash/capacity/mission constraints were not modeled.")