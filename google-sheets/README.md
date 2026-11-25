# Google Sheets: hiring tracker without extra tools

[`ats-job-changes.gs`](ats-job-changes.gs) is a self-contained Apps Script for your own spreadsheet. On every run it
starts the ATS Job Changes Feed with your Apify token, waits for it, and appends:

| Sheet | Rows | Charged |
|---|---|---|
| Jobs | New, changed, reopened and closed jobs since the previous run | per job record and closed job |
| Companies | One summary per company: open roles, new/changed/closed this run, top departments | free |
| Signals | Hiring signals (free beta), when `emitSignals` is true | free |

Each company board read is also charged once per run. On the first run for a company, `newJobs` equals all of
its open roles (the starting point), even when `emitBaseline` is false. `MAX_CHARGE_USD` caps one run.

Setup: open the script and follow the four steps at the top (paste, add `APIFY_TOKEN` as a Script Property, edit
`CONFIG`, add a time-driven trigger). The token stays in the script's properties, never in the sheet.

Other ways to fill a sheet
- n8n: [`../n8n/hiring-signals-to-google-sheets.json`](../n8n/hiring-signals-to-google-sheets.json)
- Make or Zapier: [`../no-code/make-zapier-sheets.md`](../no-code/make-zapier-sheets.md)
- Header rows to copy: [`jobs_header.csv`](jobs_header.csv), [`signals_header.csv`](signals_header.csv)

Signals describe hiring activity on public job boards; they are not proof of buying intent. Not affiliated with
Google or Apify. Built by AGI Tools Team.
