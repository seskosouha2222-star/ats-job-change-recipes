# Clay: hiring changes and hiring signals per account

Use Clay's built-in **Run Apify Actor** enrichment to add job-board activity to an account table. You run the
ATS Job Changes Feed (`agitools/ats-jobs-delta`) in your own Apify account: connect Apify to Clay with your own API
token. Nothing here needs our credentials.

## What you need in the table
One column that identifies the company's job board. The Actor does **not** accept a bare company domain. It needs
one of the following:

| Column value | Example | Notes |
|---|---|---|
| ATS board | `greenhouse:stripe`, `lever:palantir`, `ashby:openai` | Most reliable. |
| Job-board URL | `https://jobs.ashbyhq.com/openai` | Greenhouse, Lever or Ashby board URL. |
| Careers-page URL | `https://example.com/careers` | The Actor looks for a Greenhouse, Lever or Ashby link on the page (respecting robots.txt). Pages without one return a company record with an error code and are not charged. |

Call the column **Job board** (the input templates below refer to `{{Job board}}`; rename it in the JSON if your
column has another name).

Add a second, formula column **Monitor ID** that gives each account its own memory. `monitorId` accepts 1-40
letters, digits, `-` or `_`, so derive it from the domain or the board, for example with this Clay formula:

```
"clay-" + {{Domain}}.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 34)
```

Why one memory per account: Clay runs rows in parallel, and the Actor refuses to run two jobs on the same memory at
the same time (the second run stops before reading or charging anything). A per-account `monitorId` avoids that and
keeps every account's history separate.

## Recipe A: new and reopened roles per account (sales trigger)
1. **Add column → Add enrichment → Run Apify actor**, choose your Apify account, then pick **ATS Job Changes Feed**
   in **Apify actor** (type `ats-jobs-delta` to filter the list).
2. **Input data**: paste [`new-roles-input.json`](new-roles-input.json), then replace the two placeholders with real
   column references: delete `{{Job board}}`, type `/` and choose the **Job board** column; do the same for
   `{{Monitor ID}}`. Clay does not fill in typed `{{...}}` text: if a placeholder stays as text, the Actor rejects
   the input ("monitorId must be 1-40 characters") before reading anything, and Clay shows the row as failed.
3. Turn the column's **Auto-run** off while you test, or add a run condition such as "Job board is not empty", so
   blank rows do not start runs. Then run a couple of rows, check them, and run the rest.
4. Map the output (dataset items) to columns, see the mapping table below. Add a formula column such as
   "new roles this run" = count of items with `changeType` = `new`.
5. Re-run the column on a schedule (for example weekly) if your Clay plan supports it.

The first run per account is silent (`emitBaseline: false`): it returns one company record (open roles, top
departments) and stores the current openings; new and reopened roles appear from the next run on.

## Recipe B: hiring signals per account (free beta)
Paste [`hiring-signals-input.json`](hiring-signals-input.json) instead (replace the placeholders with `/` column
references as in Recipe A). It adds free `signal` records: first role in
a new department or country, first roles naming a technology, hiring acceleration or slowdown against the company's
own baseline, leadership hiring, seniority-mix shifts and a hiring-trend summary.

- Signals need history: the first run only records the company; department and country signals can appear from the
  second run, rate signals after 3+ runs over 7+ days.
- Each signal says whether it is an observed fact or an inferred signal and carries a confidence score.
- Signals describe hiring activity on the company's public job board. They are not proof of buying intent; treat
  them as one input to account scoring.

## Output mapping
| Clay column | Dataset field | Present on |
|---|---|---|
| Record type | `recordType` (`job`, `company`, `signal`) | all |
| Change | `changeType` (`new`, `changed`, `reopened`, `closed`, `unmatched`) | job |
| Job title | `title` | job |
| Department | `department` | job |
| Locations | `locations` (list), `country`, `workplaceType` | job |
| Job URL | `url` | job |
| Open roles | `openJobs` | company |
| New / closed this run | `newJobs`, `closedJobs` (on the first run `newJobs` = all open roles) | company |
| Top departments | `topDepartments` (list of `{name, jobs}`) | company |
| Signal | `signalType`, `category`, `statement` | signal |
| Signal confidence | `confidence`, `confidenceBasis` | signal |

## Cost
Pay per event on Apify: per company board read, per job record delivered and per closed job reported (see the
Actor's pricing tab on Apify). Company and signal records are free. Unchanged jobs are free in `changes` mode. Both
templates set `includeDescription: false` (smaller rows and no free text that may contain names or contact details)
and the Actor's `maxCompanies` keeps one row to one company. Set a per-run charge limit in Clay's Apify enrichment
options if available, or in the Actor's run options.

## Notes
- `companyName` is empty for Lever and Ashby boards (their APIs do not return it); use `companySlug`.
- Two tables that use the same `Monitor ID` for an account would consume each other's changes. Use a different
  prefix per table (`clay-`, `clay2-`, ...) and keep it different from your other monitors.

Tested on Clay on 2026-11-26 (Recipe A, two accounts: a `greenhouse:` board and an Ashby URL; Monitor ID formula
above; Clay's Apify connection with the user's own token).

Not affiliated with Clay or Apify. Built by AGI Tools Team.
