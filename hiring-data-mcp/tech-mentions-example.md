# Worked example: which accounts hire for the tools you sell or integrate with

A question sales, partnerships and recruiting teams ask before reaching out: *which of these companies are hiring
people to work with Kubernetes, Snowflake or Salesforce right now?* Job posts answer it with public, current
evidence. This page shows one real call to the [Hiring Data MCP Server](https://apify.com/agitools/hiring-data-mcp)
and how to read the answer.

## The prompt

> Which of greenhouse:discord, lever:palantir and ashby:notion name Kubernetes, Snowflake or Salesforce in their
> open job posts? Show the number of roles, the hiring signal and one job link per match.

The assistant makes one tool call:

```json
{
  "tool": "compare_tech_mentions",
  "arguments": {
    "companies": ["greenhouse:discord", "lever:palantir", "ashby:notion"],
    "technologies": ["Snowflake", "Kubernetes", "Salesforce"]
  }
}
```

## The answer (real output, 2026-11-28)

| Technology | Company | Roles naming it | Open jobs | Hiring signal |
|---|---|---|---|---|
| Kubernetes | Palantir | 48 | 305 | strong |
| Kubernetes | Discord | 3 | 30 | moderate |
| Kubernetes | Notion | 3 | 174 | moderate |
| Salesforce | Notion | 25 | 174 | strong |
| Salesforce | Discord | 1 | 30 | weak |
| Snowflake | Notion | 3 | 174 | moderate |

Each match comes with evidence you can open and check, for example:

```json
{
  "title": "Business Systems Engineer",
  "url": "https://jobs.ashbyhq.com/notion/30a5c739-185f-4a55-8a63-85974d687444",
  "postedAt": "2026-10-29T17:57:50Z",
  "where": "description",
  "snippet": "…trong SQL skills and experience working with a data warehouse such as Snowflake or BigQuery; you design for clean, traceable data and unders…"
}
```

Job posts change every day: run the call yourself for today's figures.

## How to read it

The server keeps three things apart, and so should you:

1. **A mention**: the technology is named in an open job post.
2. **A hiring signal**: how often it is named (number of roles, share of open jobs, job titles). `strong`,
   `moderate` or `weak`.
3. **Verified adoption**: the company bought or runs the technology. **The server never reports this**
   (`"verifiedAdoption": false` in every answer).

The evidence above shows why the difference matters: the post names "Snowflake or BigQuery" as examples of a data
warehouse. That is a real hiring signal for data-warehouse skills, and it is not proof of which warehouse the
company runs. Open the link before you write "I saw you use …" in an email.

What the server already leaves out so the counts mean something:

- text repeated in at least half of a company's posts (company boilerplate);
- names in customer, partner, investor and competitor lists ("trusted by teams at …");
- the company's own name.

Technologies a company never names in job posts are not visible at all.

## Follow-up prompts

- "Show every technology ashby:notion names in at least 5 open roles, by category." (`tech_mentions`)
- "For the Kubernetes roles at lever:palantir, list the 10 newest with location and link." (`search_jobs`)
- "Compare the same three technologies across these 10 accounts: …" (up to 10 companies and 10 technologies per
  call)

## What this call cost

One successful multi-company call: $0.01, plus the Apify platform usage of the server run in your account (256 MB,
it stops 5 minutes after the last request). A failed call (unknown company, invalid input, provider error) is free.

Not affiliated with Greenhouse, Lever, Ashby, Discord, Palantir, Notion, Snowflake, Salesforce, Apify or the
Kubernetes project. Company names appear only as examples of public job boards. Built by AGI Tools Team.
