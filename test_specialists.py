"""Checks for specialist lenses.

A lens is condensed thinking a tenant consults, not an agent that acts. The
invariants that matter: retrieval routes a situation to the right domain, the
caveats are always present, the output is explicitly advisory, and the same
situation always produces the same viewpoint.

Run:  python3 test_specialists.py
"""

from __future__ import annotations

import sys

from mvp.specialists import available_specialists, get_specialist
from mvp.specialists.base import Specialist

FAILS: list[str] = []


RECORDS: list = []


def check(label, cond, detail=""):
    ok = bool(cond)
    RECORDS.append((str(label), ok, str(detail)))
    if ok:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}{' — ' + detail if detail else ''}")
        FAILS.append(str(label))


print("== registry ==")
specs = available_specialists()
check("at least one specialist ships with core", len(specs) >= 1, str(len(specs)))
ids = [s["id"] for s in specs]
check("paul_graham lens is available", "paul_graham" in ids, str(ids))
check("registry reports principle counts", all(s["principles"].isdigit() for s in specs))

pg = get_specialist("paul_graham")
check("lens loads", pg.id == "paul_graham")
check("lens has principles", len(pg._principles) >= 20, str(len(pg._principles)))
check("lens declares its limits", len(pg.limits) >= 3, str(len(pg.limits)))
check("every principle has an essay and a url",
      all(p.get("essay") and p.get("url") for p in pg._principles))
check("principle ids are unique",
      len({p["id"] for p in pg._principles}) == len(pg._principles))

try:
    get_specialist("does_not_exist")
    check("unknown specialist raises", False, "no error raised")
except KeyError:
    check("unknown specialist raises", True)

print("== retrieval routes to the right domain ==")
cases = [
    ("A 9+1 loyalty card gives away 10% of units to increase repeat visits and frequency.",
     {"growth", "pricing"}),
    ("Should we hire a head of sales to build a pipeline for our B2B product?",
     {"hiring"}),
    ("We have too many meetings and cannot get product work done.",
     {"focus"}),
    ("Our cafe runs at thin margins and we want to grow revenue.",
     {"pricing", "growth"}),
    ("How do we improve team culture and stop arguments turning personal?",
     {"culture"}),
]
for text, expected in cases:
    got = pg.retrieve(text, k=3)
    domains = {p.domain for p in got}
    check(f"routed: {text[:42]}…", bool(domains & expected),
          f"expected one of {expected}, got {domains or 'none'}")

print("== no-match is honest, not padded ==")
v = pg.advise("What colour should the reception sofa be?", k=3)
check("nonsense situation returns no principles", len(v.principles) == 0,
      str(len(v.principles)))
check("nonsense situation says so plainly", "No principle" in v.reading)
check("no-match still carries caveats", len(v.caveats) >= 3)

print("== viewpoint shape ==")
v = pg.advise(
    "We are considering a 9+1 loyalty card that gives away 10% of units to increase repeat visits.",
    k=3,
)
d = v.to_dict()
check("viewpoint declares advisory_only", d["advisory_only"] is True)
check("viewpoint carries a note about the mutation path", "mutation" in d["note"].lower())
check("viewpoint lists principles", len(d["principles"]) >= 1)
check("principles carry a citation url", all(p["url"] for p in d["principles"]))
check("principles explain why they matched",
      all(p["matched_because"] for p in d["principles"]))
check("viewpoint raises questions", len(d["questions_to_answer"]) >= 1)
check("caveats include the lens limits", len(d["caveats"]) >= len(pg.limits))
brief = v.as_brief()
check("brief contains the essay citation", "paulgraham.com" in brief)
check("brief contains the caveat section", "does not apply" in brief.lower())

print("== tenant context tunes the reading, not the principles ==")
thin = pg.advise("We want to grow revenue.", k=3,
                 tenant_context={"operating_margin_pct": 0.4, "business_type": "cafe"})
check("thin margin injects a specific caveat",
      any("operating margin" in c for c in thin.caveats), str(thin.caveats[:2]))
check("business type is acknowledged",
      any("cafe" in c.lower() for c in thin.caveats))
base = pg.advise("We want to grow revenue.", k=3)
check("context does not change which principles fire",
      [p.id for p in thin.principles] == [p.id for p in base.principles])

print("== determinism ==")
a = pg.advise("We are considering a loyalty card.", k=3).to_dict()
b = pg.advise("We are considering a loyalty card.", k=3).to_dict()
check("same situation gives same viewpoint", a == b)
check("retrieval is stable", [p["id"] for p in a["principles"]] == [p["id"] for p in b["principles"]])

print("== a lens cannot act ==")
for forbidden in ("mutate", "apply", "dispatch", "spend", "execute"):
    check(f"specialist has no {forbidden} method", not hasattr(pg, forbidden))

print("== condensed, not dumped ==")
check("advice returns a bounded number of principles", len(pg.advise("growth", k=4).principles) <= 4)
check("principle text is condensed to one sentence",
      all(len(p["gist"]) < 400 for p in pg._principles))
check("corpus was condensed, not stored in the lens",
      "essays_ingested" in pg.spec.get("source", {}))


def test_checks(case):
    """Each recorded check is reported as its own pytest test."""
    assert case is not None, "harness recorded no checks — did it run?"
    label, ok, detail = case
    assert ok, f"{label}{' — ' + detail if detail else ''}"


if __name__ == "__main__":
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURES:")
        for f in FAILS:
            print(" -", f)
        sys.exit(1)
    print("All specialist checks passed.")
