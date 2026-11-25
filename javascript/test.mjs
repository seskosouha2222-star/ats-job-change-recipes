// Offline tests for the Node example and the Apps Script mapping (no network, no token): node --test javascript/test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { buildInput, splitRecords } from './ats-job-changes.mjs';

const require = createRequire(import.meta.url);
const { itemsToRows, SHEETS } = require('../google-sheets/ats-job-changes.gs');
const RUN2 = JSON.parse(readFileSync(new URL('../python/sample_run2_changes.json', import.meta.url), 'utf8'));

test('splitRecords groups jobs by change type', () => {
  const out = splitRecords(RUN2);
  const jobs = RUN2.filter((r) => r.recordType === 'job');
  const counted = Object.values(out.jobs).reduce((n, list) => n + list.length, 0);
  assert.equal(counted, jobs.filter((r) => out.jobs[r.changeType]).length);
  assert.ok(out.jobs.new.length > 0);
});

test('buildInput keeps memory and skips descriptions', () => {
  const inp = buildInput(['greenhouse:stripe'], { monitorId: 'abc' });
  assert.equal(inp.monitorId, 'abc');
  assert.equal(inp.includeDescription, false);
  assert.equal(inp.mode, 'changes');
});

test('itemsToRows fills each sheet with rows as wide as its header', () => {
  const items = [
    ...RUN2,
    { recordType: 'company', status: 'ok', ats: 'lever', companySlug: 'acme', openJobs: 4, newJobs: 1,
      changedJobs: 0, closedJobs: 2, topDepartments: [{ name: 'Sales', jobs: 3 }] },
    { recordType: 'signal', ats: 'lever', companySlug: 'acme', signalType: 'new_department', category: 'observed',
      statement: 'First open role in Data', confidence: 0.9, observedAt: '2026-11-25T08:00:00Z' },
  ];
  const rows = itemsToRows(items, '2026-11-25');
  for (const name of Object.keys(SHEETS)) {
    assert.ok(rows[name].length > 0, name);
    for (const row of rows[name]) assert.equal(row.length, SHEETS[name].length, name);
  }
  const acme = rows.Companies.find((r) => r[1] === 'acme');   // falls back to the slug when the name is empty
  assert.ok(acme);
  assert.equal(acme[8], 'Sales (3)');
  assert.ok(rows.Signals.some((r) => r[4] === 'new_department'));
});

// Codex P2 on PR #1: a run that outlasts the Apps Script deadline must be collected by the next invocation.
test('Apps Script resumes a run that outlasted the previous invocation', () => {
  const gsPath = require.resolve('../google-sheets/ats-job-changes.gs');
  delete require.cache[gsPath];
  const props = new Map([['APIFY_TOKEN', 'test-placeholder']]);
  const calls = [];
  let runStatus = 'RUNNING';
  const appended = [];
  globalThis.PropertiesService = { getScriptProperties: () => ({
    getProperty: (k) => props.get(k) ?? null, setProperty: (k, v) => props.set(k, v), deleteProperty: (k) => props.delete(k) }) };
  globalThis.UrlFetchApp = { fetch: (url, opts) => {
    calls.push(`${opts.method} ${url.replace('https://api.apify.com/v2', '')}`);
    const body = url.includes('/datasets/')
      ? [{ recordType: 'job', changeType: 'new', ats: 'lever', companySlug: 'acme', title: 'Data Engineer', jobId: 'j1' }]
      : { data: { id: 'RUN1', status: runStatus, defaultDatasetId: 'DS1' } };
    return { getResponseCode: () => 200, getContentText: () => JSON.stringify(body) };
  } };
  const sheet = { rows: 0, getLastRow() { return this.rows; }, appendRow() { this.rows += 1; },
    getRange: () => ({ setValues: (v) => { appended.push(...v); sheet.rows += v.length; } }) };
  globalThis.SpreadsheetApp = { getActiveSpreadsheet: () => ({ getSheetByName: () => sheet, insertSheet: () => sheet }) };
  const gs = require(gsPath);
  gs.CONFIG.MAX_WAIT_MS = -1;                       // the deadline has passed at the first check
  assert.throws(() => gs.runFeed(), /still running; the next run of this script will collect it/);
  assert.equal(props.get(gs.PENDING_KEY), 'RUN1');
  assert.equal(calls.filter((c) => c.startsWith('post ')).length, 1);
  runStatus = 'SUCCEEDED';
  gs.runFeed();
  assert.equal(calls.filter((c) => c.startsWith('post ')).length, 1, 'no second run was started');
  assert.ok(calls.includes('get /actor-runs/RUN1?waitForFinish=45'));
  assert.equal(appended.length, 1);
  assert.equal(props.has(gs.PENDING_KEY), false, 'cleared after the rows were written');
});
