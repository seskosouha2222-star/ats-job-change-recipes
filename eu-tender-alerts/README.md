# EU Tender Alerts: integration templates

Templates for [EU Tender Alerts](https://apify.com/agitools/eu-tender-alerts), an Apify Actor that watches EU public
tenders on TED (Tenders Electronic Daily) and returns only what is new since the last run: new tenders, tender updates
with the previous deadline or value, and contract awards with winners.

You run every template with your own Apify account and token. Tender data: TED, © European Union.

| Template | What it does | Tested |
|---|---|---|
| `n8n/new-tenders-to-slack.json` | Daily: new tenders and tender updates for your keywords, CPV codes and countries, one Slack message each | Offline against the Actor's schemas |
| `make/new-tenders-to-slack.blueprint.json` | The same alert on Make's Apify app, with a per-run cost cap | Offline against the Actor's schemas |
| `clay/buyer-watch-input.json` | Clay, per account: notices published by a public buyer you sell to | Input run on the Actor (2026-11-26) |
| `clay/competitor-awards-input.json` | Clay, per account: contracts a company won in the last 90 days | Input run on the Actor (2026-11-26) |
| `mcp/cursor-mcp.json`, `mcp/vscode-mcp.json` | The Actor as one tool for an AI assistant, through Apify's MCP server | Configuration shape only |

"Offline against the Actor's schemas" means: the Actor input in the template is accepted by the published input schema,
every output field the template reads exists in the dataset schema, and the workflow structure is checked by
`tests/test_eu_tender_alerts_templates.py`. The n8n and Make templates use the same request and message steps as the
ATS Job Changes Feed templates in this repository, which were run end to end; these two have not yet been run end to
end in n8n or Make.

## n8n
Import `n8n/new-tenders-to-slack.json`, create a Header Auth credential (`Authorization: Bearer <your Apify token>`),
select it in **Run EU Tender Alerts**, edit the JSON body, paste your Slack incoming-webhook URL into **Post to Slack**.
The first run records the current notices and posts nothing (`firstRun: baseline`).

## Make
Import the blueprint, connect your Apify account in the first module, edit the input JSON, and paste your Slack
incoming-webhook URL into the last module. `maxTotalChargeUsd` caps each run.

## Clay
Add a **Run Apify Actor** enrichment with Actor `agitools/eu-tender-alerts` and paste one of the inputs. Insert the
columns with `/` (typed `{{...}}` text is not filled in):

- `Buyer name` or `Company name`: the organisation's name as it appears in tender notices. Names with a double quote
  are not supported by the query.
- `Monitor ID`: 1 to 40 letters, digits, `-` or `_`, different for each row. It is the memory that keeps a notice from
  being returned twice for that row.

Each run returns the notices as records plus one `summary` record (`recordType: "summary"`) with the counts.

## AI assistants (MCP)
In Claude, add `https://mcp.apify.com?tools=agitools/eu-tender-alerts` as a custom connector. In Cursor or VS Code, use
the file in `mcp/`. You sign in to Apify when the assistant first calls the tool; no token is stored in these files.

## Input and output
`schema/input_schema.json` and `schema/dataset_schema.json` are copies of the Actor's published schemas (version 0.1.1).
Useful inputs: `keywords`, `cpvCodes` (8-digit codes include their sub-codes), `countries` (two-letter codes),
`noticeKinds` (`tenders`, `updates`, `awards`, `planning`), `minValue`, `monitorId`, `firstRun` (`deliver` or
`baseline`), `maxNoticesPerRun`.

Built by AGI Tools, the Actor's publisher. AGI Tools is not affiliated with the European Union, Apify, n8n, Make, Clay
or Slack.
