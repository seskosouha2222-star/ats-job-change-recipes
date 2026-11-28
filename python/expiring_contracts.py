#!/usr/bin/env python3
"""Keep a pipeline of expiring US federal contracts from Federal Contract Recompete Radar
(agitools/federal-recompete-radar).

The Actor returns only what moved since the last run of a watch: `new` contracts, `changed` contracts (dates or
amounts moved) and contracts that `left_window` (their end date moved out of the window you watch). This script
applies those records to a CSV pipeline and prints a short digest you can paste into a message.

Usage
  # work offline from an exported dataset (JSON array of dataset items)
  python expiring_contracts.py --from-file sample_recompete_run1.json

  # or run the Actor with your own Apify token
  export APIFY_TOKEN=<APIFY_TOKEN>
  python expiring_contracts.py --input ../federal-recompete-radar/input.json

An expiring contract is not a procurement announcement. The agency may exercise an option, extend the contract, award
a bridge, consolidate the work or stop it. `confirmedSolicitation` is false on every record: confirm any follow-on in
official solicitations before acting on it.

Built by AGI Tools Team.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ACTOR = "agitools/federal-recompete-radar"
COLUMNS = ["awardId", "status", "endDate", "potentialEndDate", "expirationKind", "obligatedUsd", "ceilingUsd",
           "incumbent", "incumbentUei", "awardingAgency", "naicsCode", "lastChange"]


def load_pipeline(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {row["awardId"]: row for row in csv.DictReader(f)}


def describe(changes: list[dict]) -> str:
    return "; ".join(f"{c['field']}: {c['before']} -> {c['after']}" for c in changes or [])


def apply(pipeline: dict[str, dict], items: list[dict]) -> dict[str, list[dict]]:
    """Apply one run's records to the pipeline. Returns the records grouped by change type."""
    seen: dict[str, list[dict]] = {"new": [], "changed": [], "left_window": []}
    for item in items:
        if item.get("recordType") != "contract" or item.get("changeType") not in seen:
            continue
        row = {k: item.get(k) for k in COLUMNS if k in item}
        # A withheld name stays empty: the recipient is identified by its UEI.
        row["incumbent"] = item.get("incumbent") or ""
        row["status"] = "left window" if item["changeType"] == "left_window" else "in window"
        row["lastChange"] = describe(item.get("changes")) if item["changeType"] != "new" else "new"
        pipeline[item["awardId"]] = {**pipeline.get(item["awardId"], {}), **row}
        seen[item["changeType"]].append(item)
    return seen


def reconcile(pipeline: dict[str, dict], today: date) -> list[str]:
    """Mark contracts whose end date has passed. Returns the award IDs marked in this call.

    The Actor reports `left_window` only when an end date MOVED out of the window. A contract that simply reaches its
    end date produces no record, so the pipeline has to notice it by itself. A later `changed` record (for example an
    extension) puts the contract back `in window`.
    """
    marked = []
    for award_id, row in pipeline.items():
        if row.get("status") != "in window":
            continue
        try:
            ended = date.fromisoformat(row.get("endDate") or "") < today
        except ValueError:
            continue                     # no usable end date: leave the row as it is
        if ended:
            row["status"] = "end date passed"
            row["lastChange"] = f"end date {row['endDate']} passed without a new record"
            marked.append(award_id)
    return marked


def save_pipeline(path: Path, pipeline: dict[str, dict]) -> None:
    rows = sorted(pipeline.values(), key=lambda r: (r.get("status") != "in window", r.get("endDate") or ""))
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def usd(value) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "amount not stated"


def digest(seen: dict[str, list[dict]], ended: list[str] | None = None) -> str:
    def who(i):
        return i.get("incumbent") or f"recipient UEI {i.get('incumbentUei')}"

    lines = []
    for item in sorted(seen["new"], key=lambda i: i.get("endDate") or ""):
        kind = "option period ends" if item.get("expirationKind") == "option_period_ends" else "current period ends"
        lines.append(f"NEW  {item['awardId']}: {kind} {item.get('endDate')} ({usd(item.get('obligatedUsd'))} obligated, {who(item)})")
    for item in seen["changed"]:
        lines.append(f"CHANGED  {item['awardId']}: {describe(item.get('changes'))}")
    for item in seen["left_window"]:
        lines.append(f"LEFT WINDOW  {item['awardId']}: {describe(item.get('changes'))}")
    for award_id in ended or []:
        lines.append(f"END DATE PASSED  {award_id}: no extension or other change was reported; no longer listed as active")
    if not lines:
        return "No new, changed or left-window contracts in this run."
    return "\n".join(lines + ["Expiring contracts are not procurement announcements; confirm any follow-on in official solicitations."])


def run_actor(run_input: dict, max_charge_usd: str) -> list[dict]:
    try:
        from apify_client import ApifyClient
    except ImportError:
        sys.exit("pip install -r requirements.txt (apify-client) to run the Actor, or use --from-file")
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        sys.exit("set APIFY_TOKEN to your own Apify API token")
    client = ApifyClient(token)
    run = client.actor(ACTOR).call(run_input=run_input, max_total_charge_usd=Decimal(max_charge_usd))
    field = lambda camel, snake: run.get(camel) if isinstance(run, dict) else getattr(run, snake)   # noqa: E731
    if field("status", "status") != "SUCCEEDED":
        sys.exit(f"Actor run did not succeed: {field('status', 'status')}")
    return list(client.dataset(field("defaultDatasetId", "default_dataset_id")).iterate_items())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-file", type=Path, help="exported dataset items (JSON array)")
    source.add_argument("--input", type=Path, help="Actor input as a JSON file; runs the Actor with APIFY_TOKEN")
    parser.add_argument("--pipeline", type=Path, default=Path("recompete_pipeline.csv"))
    parser.add_argument("--max-charge-usd", default="1.00", help="upper limit of what one run may cost (default 1.00)")
    parser.add_argument("--today", type=date.fromisoformat, default=None,
                        help="date used to recognise passed end dates, YYYY-MM-DD (default: today; for tests and replays)")
    args = parser.parse_args(argv)
    if args.from_file:
        items = json.loads(args.from_file.read_text(encoding="utf-8"))
    else:
        items = run_actor(json.loads(args.input.read_text(encoding="utf-8")), args.max_charge_usd)
    pipeline = load_pipeline(args.pipeline)
    seen = apply(pipeline, items)
    ended = reconcile(pipeline, args.today or date.today())
    # The pipeline file is written only after the whole run was applied, so a failed run never leaves it half updated.
    save_pipeline(args.pipeline, pipeline)
    print(digest(seen, ended))
    print(f"\n{len(pipeline)} contracts in {args.pipeline}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
