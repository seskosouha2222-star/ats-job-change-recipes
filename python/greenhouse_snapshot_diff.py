#!/usr/bin/env python3
"""Detect new, changed and closed jobs on one Greenhouse board with nothing but the standard library.

A minimal, dependency-free example of the snapshot-diff pattern behind a job change feed. It reads the public
Greenhouse Job Board API (`GET https://boards-api.greenhouse.io/v1/boards/<board_token>/jobs`), compares the result
with the snapshot saved by the previous run, and prints what changed as JSON lines.

Three rules keep it honest (they are the part most home-made scripts get wrong):

1. Timestamps are not changes. Greenhouse `updated_at` moves when a board is re-saved in bulk, so the fingerprint uses
   only the title, the location and the posting URL.
2. A malformed or partial answer never closes anything. The answer must have a `jobs` list, every job needs an id and
   a title, and when the API reports `meta.total` it must equal the number of jobs received. Otherwise the script exits
   with an error and leaves the snapshot untouched.
3. A job is reported closed only after it is missing from two consecutive complete reads. A board that suddenly lists
   no jobs at all needs one extra confirming read before its jobs are closed.

Usage
  python greenhouse_snapshot_diff.py stripe --state stripe.json            # live read
  python greenhouse_snapshot_diff.py stripe --state stripe.json --from-file board.json   # offline

The first run only stores the baseline (no output). Built by AGI Tools Team.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
CONFIRM_READS = 2


class IncompleteRead(Exception):
    """The answer cannot be trusted; nothing may be closed from it."""


def parse_board(payload: object) -> dict[str, dict]:
    """Validate a Job Board API answer and return {job_id: record}. Raises IncompleteRead on anything unexpected."""
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise IncompleteRead("answer has no 'jobs' list")
    jobs: dict[str, dict] = {}
    for item in payload["jobs"]:
        if not isinstance(item, dict) or item.get("id") is None or not item.get("title"):
            raise IncompleteRead("a job without an id or a title")
        location = item.get("location") if isinstance(item.get("location"), dict) else {}
        record = {
            "title": str(item["title"]).strip(),
            "location": str(location.get("name") or "").strip(),
            "url": str(item.get("absolute_url") or ""),
        }
        record["fingerprint"] = hashlib.sha256(
            json.dumps([record["title"], record["location"], record["url"]]).encode()).hexdigest()[:16]
        jobs[str(item["id"])] = record
    meta = payload.get("meta")
    if isinstance(meta, dict) and isinstance(meta.get("total"), int) and meta["total"] != len(jobs):
        raise IncompleteRead(f"meta.total={meta['total']} but {len(jobs)} distinct jobs received")
    return jobs


def diff(previous: dict, current: dict[str, dict]) -> tuple[list[dict], dict]:
    """Pure function: (previous state, current jobs) -> (change records, new state). The input is not mutated."""
    old_jobs: dict[str, dict] = previous.get("jobs", {})
    missing: dict[str, int] = dict(previous.get("missing", {}))
    changes: list[dict] = []
    new_jobs = {job_id: dict(rec) for job_id, rec in old_jobs.items()}
    baseline = not old_jobs and not previous.get("seeded")

    for job_id, rec in current.items():
        missing.pop(job_id, None)
        before = old_jobs.get(job_id)
        if before is None:
            if not baseline:
                changes.append({"changeType": "new", "jobId": job_id, **rec})
        elif before["fingerprint"] != rec["fingerprint"]:
            fields = [f for f in ("title", "location", "url") if before.get(f) != rec[f]]
            changes.append({"changeType": "changed", "jobId": job_id, "changedFields": fields, **rec})
        new_jobs[job_id] = rec

    board_emptied = bool(old_jobs) and not current
    needed = CONFIRM_READS + 1 if board_emptied else CONFIRM_READS  # an empty board is suspicious: confirm once more
    for job_id, before in old_jobs.items():
        if job_id in current:
            continue
        missing[job_id] = missing.get(job_id, 0) + 1
        if missing[job_id] >= needed:
            changes.append({"changeType": "closed", "jobId": job_id, **before})
            new_jobs.pop(job_id, None)
            missing.pop(job_id, None)

    return changes, {"jobs": new_jobs, "missing": missing, "seeded": True}


def load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(path: Path, state: dict) -> None:
    """Write atomically so a crash never leaves a half-written snapshot."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent or Path(".")), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(state, handle, indent=1, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_live(token: str) -> object:
    request = urllib.request.Request(API.format(token=token), headers={"User-Agent": "snapshot-diff-example"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (fixed https host)
        return json.load(response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("board_token", help="Greenhouse board token, e.g. stripe")
    parser.add_argument("--state", default="snapshot.json", help="snapshot file (default snapshot.json)")
    parser.add_argument("--from-file", help="read the board answer from a JSON file instead of the API")
    args = parser.parse_args(argv)
    state_path = Path(args.state)
    try:
        payload = json.loads(Path(args.from_file).read_text()) if args.from_file else read_live(args.board_token)
        current = parse_board(payload)
    except IncompleteRead as exc:
        print(f"incomplete read, snapshot left unchanged: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"read failed, snapshot left unchanged: {exc}", file=sys.stderr)
        return 2
    changes, state = diff(load_state(state_path), current)
    for change in changes:
        print(json.dumps(change, sort_keys=True))
    save_state(state_path, state)  # only after the changes were produced
    return 0


if __name__ == "__main__":
    sys.exit(main())
