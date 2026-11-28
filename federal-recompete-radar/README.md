# Expiring US federal contracts → a pipeline you can work from

[Expiring Federal Contracts Change Feed — Recompete Radar](https://apify.com/agitools/federal-recompete-radar)
(`agitools/federal-recompete-radar`) watches US federal contracts whose current period ends inside a window you choose
and returns only what moved since the last run of the watch: **new** contracts, **changed** contracts (dates or
amounts moved) and contracts that **left the window**. It reads the official award data published on USAspending.gov.
You run it in your own Apify account with your own token; nothing here needs a secret.

> An expiring contract is not a procurement announcement. The agency may exercise an option, extend the contract,
> award a bridge, consolidate the work or stop it. Every record carries `confirmedSolicitation: false`. Confirm any
> follow-on in official solicitations.

## 1. Describe the market you follow

[`input.json`](input.json):

```json
{
  "naicsCodes": ["541512"],
  "agencies": ["Department of Education"],
  "minAwardAmount": 1000000,
  "expiringWithinDays": 90,
  "maxContractsPerRun": 50,
  "monitorId": "education-it"
}
```

`monitorId` is the memory of the watch. Keep it the same on every run; use a different one for each market.

## 2. Try the pipeline offline

```bash
cd python
python expiring_contracts.py --from-file sample_recompete_run1.json --today 2026-11-28
python expiring_contracts.py --from-file sample_recompete_run2_illustration.json --today 2026-11-28
```

`--today` replays the sample on the day it was recorded. Leave it out on real runs: the script then uses the current
date and marks contracts whose end date has gone by as `end date passed`.

The first command writes `recompete_pipeline.csv` with seven contracts, soonest end date first, and prints a digest.
The second applies one changed contract and one that left the window: rows are updated, not duplicated.

- `sample_recompete_run1.json` holds selected fields of a real run of the Actor on 28 November 2026 (public award
  data).
- `sample_recompete_run2_illustration.json` was **written by hand** from the first file to show the `changed` and
  `left_window` records. It is an illustration of the record shapes, not observed data.

## 3. Run it on your market

```bash
pip install -r requirements.txt
export APIFY_TOKEN=<your Apify API token>
python expiring_contracts.py --input ../federal-recompete-radar/input.json --max-charge-usd 1.00
```

Schedule that command (cron, GitHub Actions, or an Apify schedule with a webhook to your own code) once a day or once
a week. Runs that find nothing new deliver nothing.

## What the columns mean

| Column | Meaning |
|---|---|
| `endDate` | End of the current period of performance |
| `potentialEndDate` | End date if every option is exercised |
| `expirationKind` | `option_period_ends` when a later potential end exists, `final_period_ends` when it does not |
| `obligatedUsd` | Money obligated so far |
| `ceilingUsd` | Value with all options (a ceiling, not spending) |
| `incumbent`, `incumbentUei` | Current recipient. The name is empty on awards that started before 4 April 2022 (the Actor withholds it for licensing reasons); the UEI and the link to the official record identify the recipient |
| `status` | `in window`; `left window` when the end date moved out of the window you watch; `end date passed` when the end date went by and the Actor reported no extension or other change (the script checks this on every run, because the Actor sends no record for a contract that simply ends) |
| `lastChange` | What moved in the latest record for this contract |

## Cost

The Actor charges per successful run and per contract delivered; contracts that did not change are not delivered
again. Current prices are on the Actor's page. `--max-charge-usd` is passed to Apify as the upper limit of one run.

## Data and responsibility

Award data is published by the US government; it can be late or incomplete, and a contract's dates can change after
you read them. This recipe and the Actor are independent tools, not affiliated with any government agency. Do not
compile the output into a company database for resale.

Built by AGI Tools Team.
