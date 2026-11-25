# ATS job change recipes

Working examples for turning company job boards into a **change feed**: new, changed, reopened and closed jobs from
Greenhouse, Lever and Ashby boards, delivered to Slack, a database, a spreadsheet or your own code.

The recipes use [ATS Job Changes Feed](https://apify.com/agitools/ats-jobs-delta) (`agitools/ats-jobs-delta`), an
Apify Actor that reads the vendors' official public job-board APIs and returns only what changed since the last run.
You run it in your own Apify account with your own token; nothing in this repository needs a secret.

| Recipe | What it does | Folder |
|---|---|---|
| Hiring signals | Company-level signals: first role in a new department or country, hiring surge, hiring slowdown. CSV and optional Slack post | [`python/hiring_signals.py`](python/hiring_signals.py) |
| Open-jobs table (SQLite) | Applies the feed so a table always equals the open jobs that match your filters | [`python/feed_to_sqlite.py`](python/feed_to_sqlite.py) |
| Open-jobs table (Postgres) | The same pattern in SQL, with `jsonb` staging | [`sql/postgres_upsert.sql`](sql/postgres_upsert.sql) |
| n8n: new roles to Slack | Daily schedule → run the Actor → keep `new` jobs → Slack message | [`n8n/ats-job-changes-to-slack.json`](n8n/ats-job-changes-to-slack.json) |
| Make, Zapier, Sheets, CRM | Step-by-step no-code setups | [`no-code/make-zapier-sheets.md`](no-code/make-zapier-sheets.md) |

## Quick start (Python, offline first)
```bash
cd python
python hiring_signals.py --from-file sample_run1_baseline.json   # seeds history, no signals
python hiring_signals.py --from-file sample_run2_changes.json    # 3 signals -> signals.csv
python feed_to_sqlite.py --from-file sample_run1_baseline.json --db jobs.sqlite
python feed_to_sqlite.py --from-file sample_run2_changes.json --db jobs.sqlite
```
The sample files use fictional companies. Then run it on real boards with your own token:
```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your Apify API token>
python hiring_signals.py --companies greenhouse:stripe https://jobs.ashbyhq.com/openai --monitor-id sales-signals
```

## How the feed works (the part that makes the recipes simple)
- Keep the same `monitorId` (or run a saved Task) on every run: that is the memory that makes the next run return
  only changes.
- Apply records in order: insert or update on `new`, `changed`, `reopened`; delete on `closed` and `unmatched`.
- The first run for a company returns every open job as `new` with `baseline: true`. Set `emitBaseline: false` to
  start silently.
- A `closed` record is only sent after a complete read of the board and the Actor's safety checks.

## Cost control
The Actor is pay per event (see its [pricing tab](https://apify.com/agitools/ats-jobs-delta/pricing)). Unchanged
jobs are free in changes mode. Every recipe sets a spending cap per run (`maxTotalChargeUsd`); keep it.

## Python client versions
`apify-client` 3.x returns a `Run` object (`run.default_dataset_id`), while 1.x and 2.x return a dict
(`run["defaultDatasetId"]`). The scripts here handle both.

## Tests
```bash
cd python && pip install pytest && python -m pytest -q
```

## Security
Never commit an API token or webhook URL. The scripts read `APIFY_TOKEN` and `SLACK_WEBHOOK_URL` from the
environment; the n8n workflow expects a Header Auth credential that you create in your own n8n instance.

## Data and responsibility
Job postings are published by employers. Every record links to the employer's original posting. You remain
responsible for how you use the data, including the employers' and job boards' own terms.

## License
The recipes, scripts, SQL, workflow and documentation in this repository are released under the [MIT License](LICENSE).
The license covers this repository only. The ATS Job Changes Feed Actor is a separate product, used under Apify's
terms and its own pricing.

Not affiliated with Greenhouse, Lever, Ashby or Apify. Built by AGI Tools Team.
