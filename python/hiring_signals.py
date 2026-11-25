#!/usr/bin/env python3
"""Account-level hiring signals from the ATS Job Changes Feed (agitools/ats-jobs-delta).

Turns the job-level change feed into a short list of company signals a sales, investor or research team can act on:

- new_department   a company posts its first role in a department you have not seen it hire for before
- new_country      a company posts its first role in a country you have not seen it hire in before
- hiring_surge     a company opened at least --surge-min new roles in one run
- hiring_slowdown  a company closed at least --slowdown-min roles in one run and closed more than it opened

Baseline records (the first run for a company) only seed the local history: they never raise a signal, so the
first run does not flood you with "new department" noise. Existing postings that the feed reports again (`changed`,
`unchanged` in snapshot mode, `unmatched`) also update the history, so a department or country is remembered even when
it first appeared through an edited posting, but they never count as new roles.

Usage
  # run the Actor with your own Apify token, then compute signals
  export APIFY_TOKEN=<APIFY_TOKEN>
  python hiring_signals.py --companies greenhouse:stripe https://jobs.ashbyhq.com/openai --monitor-id sales-signals

  # or work offline from an exported dataset (JSON array of dataset items)
  python hiring_signals.py --from-file sample_feed.json

  # optional: post the signals to a Slack incoming webhook
  export SLACK_WEBHOOK_URL=<SLACK_WEBHOOK_URL>

The history of departments and countries per company is kept in --state (default signals_state.json). It is only
written after the signals were produced, so a failed run never loses history.

Built by AGI Tools Team.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ACTOR = "agitools/ats-jobs-delta"
SIGNAL_TYPES = ("new_department", "new_country", "hiring_surge", "hiring_slowdown")
OBSERVED_TYPES = ("changed", "unchanged", "unmatched")


def company_key(record: dict) -> str:
    return f"{record.get('ats')}:{record.get('companySlug')}"


def compute_signals(records: list[dict], state: dict, surge_min: int = 5,
                    slowdown_min: int = 5) -> tuple[list[dict], dict]:
    """Pure function: dataset items + previous history -> (signals, new history).

    `state` maps "ats:slug" to {"departments": [...], "countries": [...]}. The input is never mutated."""
    history = {k: {"departments": set(v.get("departments", [])), "countries": set(v.get("countries", []))}
               for k, v in state.items()}
    companies: dict[str, dict] = defaultdict(lambda: {"name": None, "baseline": [], "new": [], "closed": [],
                                                      "observed": []})
    for r in records:
        if r.get("recordType") != "job":
            continue
        c = companies[company_key(r)]
        c["name"] = c["name"] or r.get("companyName")
        change = r.get("changeType")
        if change in ("new", "reopened"):
            (c["baseline"] if r.get("baseline") else c["new"]).append(r)
        elif change == "closed":
            c["closed"].append(r)
        elif change in OBSERVED_TYPES:                  # existing posting seen again: history only, never a new role
            c["observed"].append(r)

    signals: list[dict] = []
    for key in sorted(companies):
        c = companies[key]
        known = key in history
        seen = history.setdefault(key, {"departments": set(), "countries": set()})
        for job in c["baseline"] + c["observed"]:       # seed only, never signal
            _remember(seen, job)
        if known:
            signals += _first_time(key, c, seen, "department", "new_department")
            signals += _first_time(key, c, seen, "country", "new_country")
            if len(c["new"]) >= surge_min:
                signals.append(_signal(key, c, "hiring_surge", f"{len(c['new'])} new roles in one run", c["new"]))
            if len(c["closed"]) >= slowdown_min and len(c["closed"]) > len(c["new"]):
                signals.append(_signal(key, c, "hiring_slowdown",
                                       f"{len(c['closed'])} roles closed vs {len(c['new'])} opened", c["closed"]))
        for job in c["new"]:
            _remember(seen, job)
    new_state = {k: {"departments": sorted(v["departments"]), "countries": sorted(v["countries"])}
                 for k, v in sorted(history.items())}
    return signals, new_state


def _department(job: dict) -> str | None:
    return job.get("department") or job.get("team")


def _remember(seen: dict, job: dict) -> None:
    if _department(job):
        seen["departments"].add(_department(job))
    if job.get("country"):
        seen["countries"].add(job["country"])


def _first_time(key: str, c: dict, seen: dict, field: str, kind: str) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for job in c["new"]:
        value = _department(job) if field == "department" else job.get("country")
        bucket = seen["departments"] if field == "department" else seen["countries"]
        if value and value not in bucket:
            groups[value].append(job)
    return [_signal(key, c, kind, f"first {field}: {value}", jobs) for value, jobs in sorted(groups.items())]


def _signal(key: str, c: dict, kind: str, detail: str, jobs: list[dict]) -> dict:
    return {"company": key, "companyName": c["name"], "signal": kind, "detail": detail, "jobs": len(jobs),
            "examples": " | ".join(j.get("title") or "" for j in jobs[:3]),
            "urls": " ".join(j.get("url") or "" for j in jobs[:3])}


def run_actor(companies: list[str], monitor_id: str, max_charge_usd: str) -> list[dict]:
    try:
        from apify_client import ApifyClient
    except ImportError:
        sys.exit("pip install -r requirements.txt (apify-client) to run the Actor, or use --from-file")
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        sys.exit("set APIFY_TOKEN to your own Apify API token")
    client = ApifyClient(token)
    run = client.actor(ACTOR).call(
        run_input={"companies": companies, "monitorId": monitor_id, "mode": "changes"},
        max_total_charge_usd=Decimal(max_charge_usd))
    status = run_field(run, "status", "status")
    if status != "SUCCEEDED":
        sys.exit(f"Actor run did not succeed: {status}")
    return list(client.dataset(run_field(run, "defaultDatasetId", "default_dataset_id")).iterate_items())


def run_field(run, camel: str, snake: str):
    """apify-client 3.x returns a Run model (attributes); 1.x and 2.x return a dict (camelCase keys)."""
    if run is None:
        return None
    return run.get(camel) if isinstance(run, dict) else getattr(run, snake, None)


def post_to_slack(webhook: str, signals: list[dict]) -> None:
    lines = [f"*{s['companyName'] or s['company']}*: {s['signal'].replace('_', ' ')} ({s['detail']}) {s['urls']}"
             for s in signals]
    body = json.dumps({"text": "\n".join(lines) or "No hiring signals in this run."}).encode()
    req = urllib.request.Request(webhook, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (the user's own webhook URL)
        resp.read()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--companies", nargs="+", help="boards (greenhouse:stripe), board URLs or careers-page URLs")
    src.add_argument("--from-file", type=Path, help="exported dataset items (JSON array)")
    p.add_argument("--monitor-id", default="hiring-signals", help="keep it the same on every run")
    p.add_argument("--max-charge-usd", default="1", help="spending cap for one Actor run")
    p.add_argument("--state", type=Path, default=Path("signals_state.json"))
    p.add_argument("--csv", type=Path, default=Path("signals.csv"))
    p.add_argument("--surge-min", type=int, default=5)
    p.add_argument("--slowdown-min", type=int, default=5)
    a = p.parse_args(argv)

    records = (json.loads(a.from_file.read_text()) if a.from_file
               else run_actor(a.companies, a.monitor_id, a.max_charge_usd))
    state = json.loads(a.state.read_text()) if a.state.exists() else {}
    signals, new_state = compute_signals(records, state, a.surge_min, a.slowdown_min)

    with a.csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["company", "companyName", "signal", "detail", "jobs", "examples", "urls"])
        w.writeheader()
        w.writerows(signals)
    if os.environ.get("SLACK_WEBHOOK_URL"):
        post_to_slack(os.environ["SLACK_WEBHOOK_URL"], signals)
    a.state.write_text(json.dumps(new_state, indent=2))
    print(f"{len(signals)} signal(s) from {len(records)} record(s) -> {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
