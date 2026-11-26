# ATS job change recipes

Working examples for turning company job boards into a **change feed**: new, changed, reopened and closed jobs from
Greenhouse, Lever and Ashby boards, delivered to Slack, a database, a spreadsheet or your own code.

The recipes use [ATS Job Changes Feed](https://apify.com/agitools/ats-jobs-delta) (`agitools/ats-jobs-delta`), an
Apify Actor that reads the vendors' official public job-board APIs and returns only what changed since the last run.
You run it in your own Apify account with your own token; nothing in this repository needs a secret.

## Pick a recipe by what you need

| You want | Recipe | Platform |
|---|---|---|
| Sales: which target accounts are hiring, and where | [Clay: new roles per account](clay/README.md#recipe-a-new-and-reopened-roles-per-account-sales-trigger) | Clay |
| Sales and account intelligence: hiring signals (free beta) | [Clay: hiring signals per account](clay/README.md#recipe-b-hiring-signals-per-account-free-beta), [n8n → Google Sheets](n8n/hiring-signals-to-google-sheets.json), [Python CSV](python/hiring_signals.py) | Clay, n8n, Python |
| Recruiters: alert on new or reopened roles at client companies | [n8n → Slack](n8n/ats-job-changes-to-slack.json), [Make → Slack](make/README.md) | n8n, Make |
| Investors and analysts: weekly hiring per company | [n8n weekly digest → Slack](n8n/weekly-company-hiring-digest.json), [Google Sheets tracker](google-sheets/README.md) | n8n, Sheets |
| Job boards: keep postings in sync, remove expired ones | [SQLite](python/feed_to_sqlite.py), [Postgres](sql/postgres_upsert.sql), [Zapier paths](no-code/make-zapier-sheets.md#remove-expired-postings-from-a-job-board-zapier) | Code, Zapier |
| Department and location trends | [Google Sheets tracker](google-sheets/README.md) (Companies sheet), company records in any recipe | Sheets |
| Ask an AI assistant | [MCP setup for Claude, Cursor, VS Code, ChatGPT](mcp/README.md) | MCP |
| Your own code | [Python](python/), [Node.js](javascript/ats-job-changes.mjs) | Code |
| Learn the pattern: diff one Greenhouse board yourself, no Actor, standard library only | [greenhouse_snapshot_diff.py](python/greenhouse_snapshot_diff.py) (15 offline tests) | Code |

Every template uses **your own** Apify account and token, keeps its own memory (`monitorId`), caps the charge per run
and skips job descriptions by default (smaller rows, no free text that may contain names or contact details).

### What has been tested
- **Offline, on every commit** (`tests/`, `python/`, `javascript/`): every template's Actor input is validated against
  the Actor's input schema ([`schema/`](schema/), version 0.3.5), every output field a template reads exists in the
  dataset schema, workflow structure is checked, and the repository is scanned for secrets.
- **On Apify**: the Clay input format and the company-summary fields used by the digest and Sheets recipes were checked
  with a real run of the Actor (2026-11-25).
- **Not yet imported by us on the external platform**: the n8n workflows, the Make blueprint, the Apps Script and the
  Clay enrichment. They use each platform's documented formats; open an issue if an import fails.

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
- The n8n and Make templates call the Actor synchronously (up to 5 minutes). Keep watch lists small enough to finish
  in that time; a run that outlasts the call keeps running on Apify, and its changes are only in that run's dataset.
  The Apps Script tracker resumes such a run automatically.

## Cost control
The Actor is pay per event (see its [pricing tab](https://apify.com/agitools/ats-jobs-delta/pricing)). Unchanged
jobs are free in changes mode. Every recipe sets a spending cap per run (`maxTotalChargeUsd`); keep it.

## Python client versions
`apify-client` 3.x returns a `Run` object (`run.default_dataset_id`), while 1.x and 2.x return a dict
(`run["defaultDatasetId"]`). The scripts here handle both.

## Tests
```bash
pip install pytest
python -m pytest -q tests          # templates against the Actor's schemas
(cd python && python -m pytest -q) # Python recipes
node --test javascript/test.mjs    # Node example and Apps Script mapping
```

## Security
Never commit an API token or webhook URL. The scripts read `APIFY_TOKEN` and `SLACK_WEBHOOK_URL` from the
environment; the n8n workflows expect a Header Auth credential that you create in your own n8n instance; the Apps
Script reads the token from its Script Properties.

## Data and responsibility
Job postings are published by employers. Every record links to the employer's original posting. Descriptions can
contain recruiter names or contact details, which is why the templates leave them out; if you turn them on, treat
them as personal data where privacy law applies. Public availability does not remove those obligations. You remain
responsible for how you use the data, including the employers' and job boards' own terms.

Hiring signals are a free, opt-in beta. They describe hiring activity on public job boards, with a confidence score;
they do not prove purchase intent.

## License
The recipes, scripts, SQL, workflow and documentation in this repository are released under the [MIT License](LICENSE).
The license covers this repository only. The ATS Job Changes Feed Actor is a separate product, used under Apify's
terms and its own pricing.

Not affiliated with Greenhouse, Lever, Ashby, Apify, Clay, n8n, Make, Zapier or Google. Built by AGI Tools Team.
