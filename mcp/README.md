# Use the feed from AI assistants (MCP)

Apify hosts an MCP server at `https://mcp.apify.com`. The `tools` parameter limits it to the Actors you name, so
this URL gives an assistant exactly one tool, the ATS Job Changes Feed:

```
https://mcp.apify.com?tools=agitools/ats-jobs-delta
```

The tool appears as `agitools--ats-jobs-delta`. Runs use **your own** Apify account (sign in with OAuth, or send
your own API token), so they are billed to you at the Actor's pay-per-event prices.

| Client | Setup |
|---|---|
| Claude (claude.ai or Claude Desktop) | Settings → Connectors → **Add custom connector**, paste the URL above, sign in to Apify when asked. |
| Cursor | Copy [`cursor-mcp.json`](cursor-mcp.json) into `~/.cursor/mcp.json` (OAuth), or [`cursor-mcp-token.json`](cursor-mcp-token.json) to send a token read from the `APIFY_TOKEN` environment variable. |
| VS Code | Copy [`vscode-mcp.json`](vscode-mcp.json) into `.vscode/mcp.json`. |
| ChatGPT and other MCP clients | Add a custom MCP server (remote, HTTP) with the URL above, where your plan allows custom servers. |

Apify's own configurator at `https://mcp.apify.com/` generates the exact snippet for other clients.

## Prompts that work
- "Run agitools--ats-jobs-delta for greenhouse:stripe and https://jobs.ashbyhq.com/openai with monitorId
  `my-watchlist`, includeDescription false, and list the roles that are new since the last run."
- "Same watch list, emitSignals true: which companies show a new department or a hiring acceleration? Quote the
  confidence."
- "Snapshot mode for lever:palantir, titleKeywords ['sales']: how many open sales roles, by country?"

Tips
- Keep the same `monitorId` across conversations; that memory is what makes later runs return only changes.
- Ask the assistant to set `maxTotalChargeUsd` (Apify's per-run charge limit) when it calls the tool.
- Companies are ATS boards (`greenhouse:<board>`, `lever:<board>`, `ashby:<board>`), Greenhouse/Lever/Ashby
  job-board URLs or careers-page URLs, not bare domains.

Not affiliated with Apify, Anthropic, Cursor, Microsoft or OpenAI. Built by AGI Tools Team.
