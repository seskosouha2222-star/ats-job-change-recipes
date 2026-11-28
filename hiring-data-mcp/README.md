# Ask an AI assistant who is hiring (MCP server)

[Hiring Data MCP Server](https://apify.com/agitools/hiring-data-mcp) (`agitools/hiring-data-mcp`) gives an AI
assistant seven read-only tools over companies' public job boards on Greenhouse, Lever and Ashby, read through the
providers' official public APIs:

| Tool | Answers |
|---|---|
| `find_job_board` | Which board a company uses (from a careers page, a board URL or `provider:slug`) and how many jobs are open |
| `list_open_jobs` | Open jobs, newest first, filtered by department, location, remote and keywords |
| `hiring_summary` | Open jobs by department and location, remote share, seniority mix, technologies named in titles |
| `compare_hiring` | The same figures side by side for up to 10 companies |
| `search_jobs` | Jobs matching keywords across up to 10 companies |
| `tech_mentions` | Technologies a company names in its open job posts, with the number of roles, a hiring signal and evidence |
| `compare_tech_mentions` | Which of up to 10 companies name given technologies in their job posts |

Use it for live questions in a conversation. For a scheduled feed of what changed since the last run, use the
[ATS Job Changes Feed recipes](../README.md) in this repository instead.

## Connect

The server runs in **your own** Apify account and authenticates with your own Apify API token.

**Direct connection** (the server's own tools appear in your client):

| Client | Setup |
|---|---|
| Cursor | Copy [`cursor-mcp.json`](cursor-mcp.json) into `~/.cursor/mcp.json`; it reads the token from the `APIFY_TOKEN` environment variable. |
| VS Code | Copy [`vscode-mcp.json`](vscode-mcp.json) into `.vscode/mcp.json`; VS Code asks for the token once and stores it as a secret. |
| Other clients | Endpoint `https://agitools--hiring-data-mcp.apify.actor/mcp`, Streamable HTTP, header `Authorization: Bearer <your Apify token>`. |

**Through Apify's MCP server** (for clients that sign in with OAuth, such as Claude): connect
`https://mcp.apify.com` (Claude: Settings → Connectors → **Add custom connector**, then sign in to Apify), or use
[`apify-mcp-cursor.json`](apify-mcp-cursor.json) in Cursor. Its `fetch-actor-mcp-tool-list` and `call-actor-mcp-tool`
tools call this server for you: ask "Use the MCP tools of agitools/hiring-data-mcp to …".

Starting the Actor with the Start button does nothing: it works only through its MCP endpoint.

## Prompts that work
- "Find the job board of notion.com/careers and summarise what they are hiring for."
- "Compare open engineering roles at greenhouse:stripe, lever:palantir and ashby:notion: who has the largest remote
  share?"
- "Search security engineer jobs at greenhouse:stripe and ashby:notion and list the remote ones with their links."
- "List the newest 10 sales jobs at lever:palantir in London."
- "Which of greenhouse:discord, lever:palantir and ashby:notion name Kubernetes, Snowflake or Salesforce in their
  open job posts? Show one job link per match." ([worked example with real output](tech-mentions-example.md))

## What it costs
- $0.005 per successful one-company call, $0.01 per successful multi-company call. Connecting, listing the tools and
  failed calls (unknown company, invalid input, provider error) are free.
- **Plus Apify platform usage** for the server run in your account: it uses 256 MB and stops 5 minutes after the last
  request. A 6-minute session measured on 2026-11-27 used about $0.005 of platform usage.
- Set a spending limit on the run (Apify's maximum charge per run) if you share the token with an agent; the server
  refuses calls that would go over it.

## Limits
- Up to 10 companies per call and 100 jobs per answer; board reads are cached for up to 10 minutes.
- Greenhouse, Lever and Ashby only; Greenhouse pay ranges are not included yet.
- Technology results are mentions in job posts and hiring signals. They are not proof that a company bought or
  runs a technology.
- No applicant data and no contact details; job descriptions only on request, cut to 1,500 characters.

Not affiliated with Greenhouse, Lever, Ashby, Apify, Anthropic, Cursor or Microsoft. Built by AGI Tools Team.
