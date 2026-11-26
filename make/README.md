# Make: new roles to Slack (importable blueprint)

[`ats-job-changes-to-slack.blueprint.json`](ats-job-changes-to-slack.blueprint.json) uses Make's official **Apify**
app plus Make's built-in JSON and HTTP modules:

1. **Apify → Run an Actor** runs ATS Job Changes Feed (`agitools/ats-jobs-delta`) synchronously for your companies,
   with **Maximum cost per run** set to $1.
2. **Apify → Get Dataset Items** returns the run's records, one bundle each (up to 500 per run).
3. A filter keeps `job` records whose `changeType` is `new` or `reopened`; **JSON → Transform to JSON** encodes the
   message, so job titles with quotes, backslashes or line breaks still make a valid request.
4. **HTTP → Make a request** posts it to a Slack incoming webhook.

Your Apify account is connected once, in Make (Apify module → **Add** connection → sign in with Apify, or paste an
API token). The blueprint contains no token and no connection, so nothing secret is shared when you share it.

## Set up
1. Scenarios → **Create a new scenario** → ⋯ → **Import blueprint** → choose the file.
2. Module 1: pick your Apify connection; edit `companies` (a board such as `greenhouse:stripe`, a job-board URL or a
   careers-page URL), `titleKeywords` and the other filters in **Input JSON**.
3. Module 4: replace the URL with your Slack incoming-webhook URL.
4. Schedule the scenario (daily is typical). Keep `monitorId` unchanged: it is the memory that returns only changes.

Good to know
- The first run with `emitBaseline: false` stores the current openings silently; alerts start with the next run.
  Re-running is safe: a role is reported once, when it appears (or reappears).
- Keep the watch list small enough for the run to finish within your Make plan's scenario timeout (a few dozen boards
  without descriptions finish in well under a minute). A run that outlasts it keeps running on Apify; use **Apify →
  Watch Actor Runs** as the trigger instead for large lists.
- Lever and Ashby boards do not return a company name; the message falls back to the board name.

Prefer Make's Slack or Google Sheets modules? Replace module 4; see
[`../no-code/make-zapier-sheets.md`](../no-code/make-zapier-sheets.md).

Also available as a Make template:
[New roles at target companies to Slack](https://www.make.com/en/integration/25728-new-roles-at-target-companies-to-slack-ats-job-changes-feed?templatePublicId=25728)
(open it in Make and follow the setup wizard).

Status: tested on make.com on 2026-11-26 (import, a run into a Slack channel, and a repeat run that posted nothing).
See "What has been tested" in the [main README](../README.md#what-has-been-tested).

Not affiliated with Make or Apify. Built by AGI Tools Team.
