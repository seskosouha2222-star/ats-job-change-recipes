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
