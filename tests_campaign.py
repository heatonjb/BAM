"""Checks for public-data prospecting and outreach composition."""
import sys
sys.path.insert(0, "/root/code/personal/research/business-as-machine")
from mvp.campaign import publicdata as P

FAILS = []
def check(l, c, d=""):
    print(("  PASS  " if c else "  FAIL  ") + l + ("" if c else f" — {d}"))
    if not c: FAILS.append(l)

recs, source = P.load_records(P.CompaniesHouseClient(api_key=""), "")
print("source:", source, "records:", len(recs))
check("falls back to fixtures without a key", source == "fixture" and len(recs) == 4)

cafe = next(r for r in recs if "Harbour" in r.name)
check("SIC 56102 maps to coffee_shop", cafe.business_type == "coffee_shop", cafe.business_type)
dev = next(r for r in recs if "Northwind" in r.name)
check("SIC 62012 maps to developer_tools", dev.business_type == "developer_tools", dev.business_type)

m = P.build_provisional_model(cafe)
labelled = {x.name: x.provenance for x in m["metrics"]}
check("revenue is labelled assumed", labelled["annual_revenue"] == "assumed")
check("gross margin is labelled derived", labelled["gross_margin"] == "derived")
check("filed facts are separate from assumptions", "sic_codes" in m["filed_facts"])
check("confidence is low for micro-entity", m["confidence"] == "low")

ins = P.insights_for(m)
check("insights produced", len(ins) >= 2, str(len(ins)))
check("insights sorted by strength",
      all(ins[i].strength >= ins[i+1].strength for i in range(len(ins)-1)))

old = next(r for r in recs if "Ridgeway" in r.name)
check("stale accounts detected", old.accounts_overdue)
m2 = P.build_provisional_model(old)
check("overdue filing ranks top", "overdue" in P.insights_for(m2)[0].headline.lower())

msg = P.compose(cafe, ins)
check("message composed", msg is not None)
check("subject is built from the top insight", ins[0].headline in msg.subject)
check("sender is identified", "Jon Heaton" in msg.body)
check("opt-out present", "Reply 'no'" in msg.body)
check("compliance block records the basis", msg.compliance["basis"] == "legitimate_interest_b2b")
check("no fabricated precision in body", "state" not in msg.body.lower())

dissolved = next(r for r in recs if "Quiet" in r.name)
check("dissolved company is ineligible", not P.eligible(dissolved, []))
check("suppressed address is ineligible", not P.eligible(cafe, [cafe.contact_email]))

res = P.run_campaign(recs, suppressed=[])
print("candidates:", res["count"], "skipped:", [s["company"] for s in res["skipped"]])
check("dissolved skipped", any("Quiet" in s["company"] for s in res["skipped"]))
check("candidates carry a model and a message",
      all("model" in c and "message" in c for c in res["candidates"]))
check("nothing claims to have been sent", "sent" not in str(res["candidates"][0]["message"]).lower())

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES"); [print(" -", f) for f in FAILS]; sys.exit(1)
print("All campaign checks passed.")
