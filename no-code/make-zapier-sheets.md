# No-code recipes: Make, Zapier, Google Sheets, Slack

All recipes start the same way, in the Apify Console:

1. Open **ATS Job Changes Feed** (`agitools/ats-jobs-delta`) and click **Save as a new task**.
2. Enter the companies to watch (a board such as `greenhouse:stripe`, a job-board URL, or a careers-page URL) and
   any title or location filters. Set **emitBaseline** to `false` if you only want jobs posted from now on.
3. Set **Max total charge** on the task to cap what one run can cost.
4. **Schedules** → run the task daily. A task keeps its own memory, so every run returns only what changed.

## Slack alert for every new role (Make)
1. Trigger: **Apify → Watch Task Runs** (your task, status succeeded).
2. **Apify → Get Dataset Items**: dataset = the run's default dataset, view `jobs`.
3. **Filter**: `changeType` equals `new`.
4. **Slack → Create a Message**: `New role at {{companyName}}{{companySlug}}: {{title}} {{url}}`.

## Remove expired postings from a job board (Zapier)
1. Trigger: **Apify → Finished Task Run**.
2. Action: **Apify → Fetch Dataset Items** (view `jobs`).
3. Paths: `changeType` = `new` → create the posting; `changed` → update it; `closed` or `unmatched` → unpublish it.
   Use `ats` + `companySlug` + `jobId` as the posting's external ID.

## Hiring tracker in Google Sheets (Make or Zapier)
1. Same trigger and dataset step as above (view `jobs`).
2. **Google Sheets → Add a Row** with `companySlug`, `companyName`, `changeType`, `title`, `department`, `country`,
   `url` and the run date. Each run appends only the changes.
3. Add a pivot table on `companySlug` and `changeType` for a weekly hiring view.

## HubSpot or Salesforce account notes (Make)
Same as the Slack recipe, but in step 4 search the CRM company by domain or name and add a note:
"Opened a {{department}} role: {{title}} ({{locations}})". Sales teams use this as a hiring trigger.

Notes
- `companyName` is empty for Lever and Ashby boards (their APIs do not return it); use `companySlug` as the fallback.
- Closed jobs are reported only after a complete read of the board and the Actor's safety checks.
- Pricing is pay per event and shown on the Actor's pricing tab; unchanged jobs are free in changes mode.

Built by AGI Tools Team.
