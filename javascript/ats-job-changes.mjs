#!/usr/bin/env node
// ATS Job Changes Feed from Node.js: run the Actor with your own token and split the result by record type.
//
//   npm install apify-client
//   APIFY_TOKEN=<your token> node ats-job-changes.mjs greenhouse:stripe https://jobs.ashbyhq.com/openai
//   node ats-job-changes.mjs --from-file ../python/sample_run2_changes.json      # offline, no token
//
// Built by AGI Tools Team. MIT License.
import { readFile } from 'node:fs/promises';

export const ACTOR = 'agitools/ats-jobs-delta';

export function buildInput(companies, { monitorId = 'node-watchlist', signals = true } = {}) {
  return { companies, monitorId, mode: 'changes', emitBaseline: false, emitSignals: signals,
           includeDescription: false, emitCompanySummaries: true };
}

/** Pure: dataset items -> { jobs: {new, changed, reopened, closed, unmatched}, companies, signals }. */
export function splitRecords(items) {
  const out = { jobs: { new: [], changed: [], reopened: [], closed: [], unmatched: [] }, companies: [], signals: [] };
  for (const r of items) {
    if (r.recordType === 'job' && out.jobs[r.changeType]) out.jobs[r.changeType].push(r);
    else if (r.recordType === 'company') out.companies.push(r);
    else if (r.recordType === 'signal') out.signals.push(r);
  }
  return out;
}

export async function runFeed(companies, { token = process.env.APIFY_TOKEN, maxTotalChargeUsd = 1 } = {}) {
  if (!token) throw new Error('Set APIFY_TOKEN (your Apify API token).');
  const { ApifyClient } = await import('apify-client');
  const client = new ApifyClient({ token });
  const run = await client.actor(ACTOR).call(buildInput(companies), { maxTotalChargeUsd });
  const { items } = await client.dataset(run.defaultDatasetId).listItems({ clean: true });
  return items;
}

async function main(argv) {
  const items = argv[0] === '--from-file'
    ? JSON.parse(await readFile(argv[1], 'utf8'))
    : await runFeed(argv.length ? argv : ['greenhouse:stripe']);
  const { jobs, companies, signals } = splitRecords(items);
  for (const j of [...jobs.new, ...jobs.reopened]) {
    console.log(`${j.changeType.padEnd(8)} ${j.companyName || j.companySlug}: ${j.title} ${j.url}`);
  }
  for (const j of jobs.closed) console.log(`closed   ${j.companyName || j.companySlug}: ${j.title}`);
  for (const c of companies) console.log(`company  ${c.companyName || c.companySlug}: ${c.openJobs ?? '-'} open`);
  for (const s of signals) console.log(`signal   ${s.companyName || s.companySlug}: ${s.statement} (confidence ${s.confidence})`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).catch((e) => { console.error(e.message); process.exit(1); });
}
