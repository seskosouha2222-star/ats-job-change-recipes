# Make: new roles to Slack (importable blueprint)

[`ats-job-changes-to-slack.blueprint.json`](ats-job-changes-to-slack.blueprint.json) uses only Make's built-in HTTP
module and Iterator, so it imports into any Make account without extra apps:

1. **HTTP** runs the ATS Job Changes Feed (`run-sync-get-dataset-items`) for your companies with a per-run charge cap.
2. **Iterator** splits the returned records.
3. A filter keeps `job` records whose `changeType` is `new` or `reopened`; **JSON → Transform to JSON** encodes the
   message, so job titles with quotes, backslashes or line breaks still make a valid request.
4. **HTTP** posts it to a Slack incoming webhook.

Import: Scenarios → **Create a new scenario** → ⋯ → **Import Blueprint**. Then:
- in module 1, replace `YOUR_APIFY_TOKEN` with your own Apify API token (or move the header into a Make keychain
  connection) and edit the companies and filters in the request body;
- in module 4, paste your Slack incoming-webhook URL;
- schedule the scenario (for example daily). Keep `monitorId` unchanged: it is the memory that returns only changes.
- keep the watch list small enough for a run to finish within the synchronous call's 5 minutes (a few dozen boards
  without descriptions finish in well under a minute). A run that outlasts the call keeps running on Apify and its
  changes are only in that run's dataset (Apify Console → Runs).

Prefer Make's apps? The same flow works with Apify's own Make app (**Run an Actor** or **Watch Actor Runs** → **Get
Dataset Items**) and Make's Slack or Google Sheets modules; see [`../no-code/make-zapier-sheets.md`](../no-code/make-zapier-sheets.md).

Status: the blueprint structure is checked by this repository's offline tests (modules, filter, Actor input against
the Actor's input schema). Import on make.com has not yet been verified by us; please open an issue if a module needs
an update.

Not affiliated with Make or Apify. Built by AGI Tools Team.
