#!/usr/bin/env python3
"""Run the public-data prospecting pipeline and write candidate emails to disk.

Nothing is sent. Output is a JSON file plus a flat CSV of subject lines for
review, because a model that writes persuasive email at volume should have a
human in the loop before anything leaves the building.

Usage:
    python scripts/campaign_run.py --query "coffee" --limit 10
    python scripts/campaign_run.py --offline          # use fixtures
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mvp.campaign import publicdata as P


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query", default="", help="Companies House search query")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--offline", action="store_true", help="use bundled fixtures")
    ap.add_argument("--out", default="data/campaign/outreach.json")
    ap.add_argument("--csv", default="data/campaign/outreach.csv")
    ap.add_argument("--suppress", default="data/campaign/suppression.txt",
                    help="one email address per line")
    args = ap.parse_args()

    suppressed = []
    if os.path.isfile(args.suppress):
        with open(args.suppress) as fh:
            suppressed = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]

    if args.offline:
        records, source = P.FixtureProvider().all(), "fixture"
    else:
        client = P.CompaniesHouseClient()
        if not client.available():
            print("COMPANIES_HOUSE_API_KEY not set — falling back to fixtures.", file=sys.stderr)
            records, source = P.FixtureProvider().all(), "fixture"
        else:
            try:
                records, source = client.search(args.query), "companies_house"
            except Exception as exc:
                # A firewalled host or a bad key must degrade, not crash a batch.
                print(f"Companies House unavailable ({exc}) — using fixtures.", file=sys.stderr)
                records, source = P.FixtureProvider().all(), "fixture"

    if args.query and source == "fixture":
        needle = args.query.lower()
        records = [r for r in records if needle in r.name.lower()] or records

    result = P.run_campaign(records, suppressed=suppressed, limit=args.limit)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump({"source": source, **result}, fh, indent=2)

    with open(args.csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["company", "number", "email", "subject", "insight_basis", "confidence"])
        for c in result["candidates"]:
            w.writerow([c["company"], c["number"], c["message"]["to"],
                        c["message"]["subject"], c["message"]["insight_basis"],
                        c["model"]["confidence"]])

    print(f"source: {source}")
    print(f"candidates: {result['count']}  skipped: {len(result['skipped'])}")
    for c in result["candidates"][:5]:
        print(f"  {c['company']:32} {c['message']['subject'][:60]}")
    print(f"\nwritten: {args.out}\nwritten: {args.csv}")
    print("Nothing has been sent. Review before dispatch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
