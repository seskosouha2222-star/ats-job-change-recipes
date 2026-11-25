#!/usr/bin/env python3
"""Keep a table of open jobs in sync with the ATS Job Changes Feed (agitools/ats-jobs-delta).

The feed is designed to be applied in order: insert or update on `new`, `changed`, `reopened` (and `unchanged` in
snapshot mode); delete on `closed` and `unmatched`. After every run the table equals the open jobs that match your
current filters. This script does that for SQLite; `../sql/postgres_upsert.sql` shows the same pattern for Postgres.

Usage
  python feed_to_sqlite.py --db jobs.sqlite --from-file dataset_items.json

Export the dataset items of a run with the Apify API (your own token):
  curl "https://api.apify.com/v2/datasets/<datasetId>/items?view=jobs&format=json" \\
       -H "Authorization: Bearer <APIFY_TOKEN>" > dataset_items.json

Built by AGI Tools Team.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS open_jobs (
    ats TEXT NOT NULL,
    company_slug TEXT NOT NULL,
    job_id TEXT NOT NULL,
    company_name TEXT,
    title TEXT,
    department TEXT,
    team TEXT,
    locations TEXT,          -- JSON array
    country TEXT,
    workplace_type TEXT,
    employment_type TEXT,
    salary TEXT,             -- JSON object or NULL
    url TEXT,
    apply_url TEXT,
    published_at TEXT,
    first_seen_at TEXT,
    last_change TEXT,
    PRIMARY KEY (ats, company_slug, job_id)
);
"""
UPSERT_TYPES = ("new", "changed", "reopened", "unchanged")
DELETE_TYPES = ("closed", "unmatched")

UPSERT_SQL = """
INSERT INTO open_jobs (ats, company_slug, job_id, company_name, title, department, team, locations, country,
                       workplace_type, employment_type, salary, url, apply_url, published_at, first_seen_at,
                       last_change)
VALUES (:ats, :companySlug, :jobId, :companyName, :title, :department, :team, :locations, :country,
        :workplaceType, :employmentType, :salary, :url, :applyUrl, :publishedAt, :firstSeenAt, :changeType)
ON CONFLICT (ats, company_slug, job_id) DO UPDATE SET
    company_name = excluded.company_name, title = excluded.title, department = excluded.department,
    team = excluded.team, locations = excluded.locations, country = excluded.country,
    workplace_type = excluded.workplace_type, employment_type = excluded.employment_type,
    salary = excluded.salary, url = excluded.url, apply_url = excluded.apply_url,
    published_at = excluded.published_at, last_change = excluded.last_change
"""
DELETE_SQL = "DELETE FROM open_jobs WHERE ats = :ats AND company_slug = :companySlug AND job_id = :jobId"
FIELDS = ("ats", "companySlug", "jobId", "companyName", "title", "department", "team", "country", "workplaceType",
          "employmentType", "url", "applyUrl", "publishedAt", "firstSeenAt", "changeType")


def apply_changes(conn: sqlite3.Connection, records: list[dict]) -> Counter:
    """Apply dataset items in order inside one transaction. Company summary records are skipped."""
    conn.executescript(SCHEMA)
    counts: Counter = Counter()
    with conn:
        for r in records:
            if r.get("recordType") != "job":
                counts["skipped"] += 1
                continue
            change = r.get("changeType")
            row = {f: r.get(f) for f in FIELDS}
            if change in UPSERT_TYPES:
                row["locations"] = json.dumps(r.get("locations") or [])
                row["salary"] = json.dumps(r["salary"]) if r.get("salary") else None
                conn.execute(UPSERT_SQL, row)
                counts["upserted"] += 1
            elif change in DELETE_TYPES:
                conn.execute(DELETE_SQL, row)
                counts["deleted"] += 1
            else:
                counts["unknown"] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Apply an ATS Job Changes Feed dataset to a SQLite table.")
    p.add_argument("--db", type=Path, default=Path("jobs.sqlite"))
    p.add_argument("--from-file", type=Path, required=True, help="dataset items (JSON array)")
    a = p.parse_args(argv)
    records = json.loads(a.from_file.read_text())
    conn = sqlite3.connect(a.db)
    counts = apply_changes(conn, records)
    total = conn.execute("SELECT COUNT(*) FROM open_jobs").fetchone()[0]
    print(f"upserted {counts['upserted']}, deleted {counts['deleted']}, skipped {counts['skipped']}; "
          f"open jobs in table: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
