/**
 * ATS Job Changes Feed -> Google Sheets (Apps Script).
 *
 * Setup (in your own spreadsheet):
 *   1. Extensions -> Apps Script, paste this file, save.
 *   2. Project Settings -> Script Properties: add APIFY_TOKEN = your Apify API token. It stays in your script; it is
 *      never written to the sheet.
 *   3. Edit CONFIG below (companies, filters, monitorId), run `runFeed` once and authorise it.
 *   4. Triggers -> Add trigger -> runFeed, time-driven, daily or weekly.
 *
 * Each run appends only what changed since the previous run: job changes to the "Jobs" sheet, free company summaries
 * to "Companies" and, if emitSignals is true, free hiring signals (beta) to "Signals". Header rows are created on
 * first use. Pay per event on Apify, capped per run by MAX_CHARGE_USD.
 *
 * Not affiliated with Google or Apify. Built by AGI Tools Team. MIT License.
 */

var CONFIG = {
  input: {
    companies: ['greenhouse:stripe', 'https://jobs.ashbyhq.com/openai'],
    monitorId: 'sheets-hiring-tracker',
    mode: 'changes',
    emitBaseline: false,
    emitSignals: true,
    includeDescription: false,
    emitCompanySummaries: true,
    titleKeywords: []
  },
  MAX_CHARGE_USD: '1'
};

var ACTOR = 'agitools~ats-jobs-delta';

var SHEETS = {
  Jobs: ['runDate', 'changeType', 'company', 'ats', 'title', 'department', 'locations', 'country',
         'workplaceType', 'url', 'publishedAt', 'firstSeenAt', 'closedAt', 'jobId'],
  Companies: ['runDate', 'company', 'ats', 'status', 'openJobs', 'newJobs', 'changedJobs', 'closedJobs',
              'topDepartments', 'errorCode'],
  Signals: ['runDate', 'observedAt', 'company', 'ats', 'signalType', 'category', 'statement', 'confidence',
            'monitoringSince']
};

/** Pure: dataset items -> rows per sheet. Exported for the offline tests. */
function itemsToRows(items, runDate) {
  var out = { Jobs: [], Companies: [], Signals: [] };
  (items || []).forEach(function (r) {
    var company = r.companyName || r.companySlug || '';
    if (r.recordType === 'job') {
      out.Jobs.push([runDate, r.changeType, company, r.ats, r.title, r.department || '',
        (r.locations || []).join('; '), r.country || '', r.workplaceType || '', r.url || '',
        r.publishedAt || '', r.firstSeenAt || '', r.closedAt || '', r.jobId]);
    } else if (r.recordType === 'company') {
      out.Companies.push([runDate, company, r.ats, r.status || '', valueOr(r.openJobs), valueOr(r.newJobs),
        valueOr(r.changedJobs), valueOr(r.closedJobs),
        (r.topDepartments || []).slice(0, 5).map(function (d) { return d.name + ' (' + d.jobs + ')'; }).join('; '),
        r.errorCode || '']);
    } else if (r.recordType === 'signal') {
      out.Signals.push([runDate, r.observedAt || '', company, r.ats, r.signalType, r.category || '',
        r.statement || '', valueOr(r.confidence), r.monitoringSince || '']);
    }
  });
  return out;
}

function valueOr(v) { return v === null || v === undefined ? '' : v; }

function runFeed() {
  var apifyToken = PropertiesService.getScriptProperties().getProperty('APIFY_TOKEN');
  if (!apifyToken) throw new Error('Add APIFY_TOKEN in Project Settings -> Script Properties.');
  var api = 'https://api.apify.com/v2';
  // Start the run, then wait in short steps: Apps Script requests time out after about a minute.
  var run = apifyJson(apifyToken, 'post', api + '/acts/' + ACTOR + '/runs?waitForFinish=45&maxTotalChargeUsd=' +
    encodeURIComponent(CONFIG.MAX_CHARGE_USD), CONFIG.input).data;
  var deadline = Date.now() + 5 * 60 * 1000;   // stay inside the 6-minute Apps Script limit
  while (['READY', 'RUNNING'].indexOf(run.status) >= 0) {
    if (Date.now() > deadline) throw new Error('Run ' + run.id + ' still running; it will finish on Apify. Re-run later.');
    run = apifyJson(apifyToken, 'get', api + '/actor-runs/' + run.id + '?waitForFinish=45').data;
  }
  if (run.status !== 'SUCCEEDED') throw new Error('Run ' + run.id + ' ended with status ' + run.status);
  var items = apifyJson(apifyToken, 'get', api + '/datasets/' + run.defaultDatasetId + '/items?clean=true&format=json');
  var rows = itemsToRows(items, new Date().toISOString().slice(0, 10));
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  Object.keys(SHEETS).forEach(function (name) {
    if (!rows[name].length) return;
    var sh = ss.getSheetByName(name) || ss.insertSheet(name);
    if (sh.getLastRow() === 0) sh.appendRow(SHEETS[name]);
    sh.getRange(sh.getLastRow() + 1, 1, rows[name].length, SHEETS[name].length).setValues(rows[name]);
  });
}

function apifyJson(apifyToken, method, url, body) {
  var opts = { method: method, headers: { Authorization: 'Bearer ' + apifyToken }, muteHttpExceptions: true };
  if (body) { opts.contentType = 'application/json'; opts.payload = JSON.stringify(body); }
  var res = UrlFetchApp.fetch(url, opts);
  var code = res.getResponseCode();
  if (code < 200 || code >= 300) throw new Error('Apify returned HTTP ' + code + ': ' + res.getContentText().slice(0, 300));
  return JSON.parse(res.getContentText());
}

if (typeof module !== 'undefined') module.exports = { itemsToRows: itemsToRows, SHEETS: SHEETS, CONFIG: CONFIG };
