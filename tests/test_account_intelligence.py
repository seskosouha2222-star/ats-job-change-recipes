"""Offline checks for n8n/account-hiring-intelligence.json (no network, no token).

Every n8n expression and Code node is evaluated by Node.js against records shaped exactly like the Actor's output
(fields copied from dev run wymPtZgyJYW0LuBFZ, 2026-11-26). What this cannot check: the n8n editor itself, Google
Sheets and Slack. Those need the end-to-end run listed in the README before the template is submitted."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WF = json.loads((ROOT / "n8n/account-hiring-intelligence.json").read_text())
NODES = {n["name"]: n for n in WF["nodes"]}

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

CONFIG = {a["name"]: (json.loads(a["value"]) if a["type"] == "array" else float(a["value"]) if a["type"] == "number"
                      else a["value"])
          for a in NODES["Configuration"]["parameters"]["assignments"]["assignments"]}

JOB_NEW = {"recordType": "job", "changeType": "new", "ats": "ashby", "companySlug": "openai", "companyName": None,
           "jobId": "f9818cd7", "title": "Applied AI Architect, Large Enterprise", "department": "Go To Market",
           "locations": ["Paris, France"], "url": "https://jobs.ashbyhq.com/openai/f9818cd7", "changedFields": [],
           "firstSeenAt": "2026-11-26T07:50:35Z", "closedAt": None}
JOB_CHANGED = {**JOB_NEW, "changeType": "changed", "jobId": "6238480004", "companySlug": "figma",
               "companyName": "Figma", "title": "Applied Data Researcher", "changedFields": ["descriptionHash"]}
JOB_REOPENED = {**JOB_NEW, "changeType": "reopened", "jobId": "r1", "title": "Solutions Engineer"}
COMPANY_OK = {"recordType": "company", "status": "ok", "ats": "greenhouse", "companySlug": "stripe",
              "companyName": "Stripe", "openJobs": 772, "newJobs": 7, "changedJobs": 2, "closedJobs": 0,
              "remoteShare": 0, "topDepartments": [{"name": "Account Executives (EMEA)", "jobs": 53},
                                                   {"name": "Product Design", "jobs": 14},
                                                   {"name": "Security Analytics", "jobs": 13},
                                                   {"name": "Marketing", "jobs": 12}]}
COMPANY_ERR = {"recordType": "company", "status": "error", "ats": "lever", "companySlug": "gone", "companyName": None,
               "errorCode": "board_not_found"}
SIG_KEEP = {"recordType": "signal", "signalType": "new_department", "category": "observed_fact", "ats": "greenhouse",
            "companySlug": "stripe", "companyName": "Stripe", "confidence": 0.9,
            "statement": "First open role in department 'Revenue Operations'", "interpretation": None,
            "observedAt": "2026-11-26T07:50:35Z", "evidence": [{"title": "RevOps Manager"}, {"title": "RevOps Analyst"}]}
SIG_LOW = {**SIG_KEEP, "signalType": "geographic_expansion", "confidence": 0.3, "statement": "low confidence"}
SIG_TREND = {**SIG_KEEP, "signalType": "hiring_trend", "confidence": None, "statement": "772 open roles"}

STUB = ("const $now = { toISODate: () => '2026-11-26', toISO: () => '2026-11-26T08:00:00.000Z' };"
        f"const $ = (name) => ({{ first: () => ({{ json: {json.dumps(CONFIG)} }}) }});")


def node_js(script: str) -> str:
    return subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout


def eval_expr(expr: str, record: dict):
    inner = re.fullmatch(r"=\{\{(.*)\}\}", expr, re.S).group(1)
    return json.loads(node_js(f"{STUB} const $json = {json.dumps(record)}; console.log(JSON.stringify({inner}));"))


def set_row(name: str, record: dict) -> dict:
    return {a["name"]: eval_expr(a["value"], record)
            for a in NODES[name]["parameters"]["assignments"]["assignments"]}


def run_code(name: str, records: list[dict]) -> list[dict]:
    js = NODES[name]["parameters"]["jsCode"]
    harness = (f"{STUB} const $input = {{ all: () => {json.dumps(records)}.map(json => ({{ json }})) }};"
               f"console.log(JSON.stringify((() => {{ {js} }})()));")
    return json.loads(node_js(harness))


def targets(src: str, output: int) -> set[str]:
    return {e["node"] for e in WF["connections"][src]["main"][output]}


def test_actor_input_asks_for_changes_summaries_and_signals():
    body = re.fullmatch(r"=\{\{(.*)\}\}", NODES["Run ATS Job Changes Feed"]["parameters"]["jsonBody"], re.S).group(1)
    inp = json.loads(node_js(f"const $json = {json.dumps(CONFIG)}; console.log({body});"))
    assert inp["companies"] == CONFIG["companies"] and inp["monitorId"] == CONFIG["monitorId"]
    assert inp["emitSignals"] and inp["emitCompanySummaries"] and inp["includeClosed"]
    assert inp["emitBaseline"] is False and inp["includeDescription"] is False and inp["mode"] == "changes"


def test_wiring_routes_every_record_type_and_failure():
    assert NODES["Run ATS Job Changes Feed"]["onError"] == "continueErrorOutput"
    assert targets("Run ATS Job Changes Feed", 0) == {"Route by record type", "Build account digest"}
    assert targets("Run ATS Job Changes Feed", 1) == {"Alert: run failed"}
    keys = [r["outputKey"] for r in NODES["Route by record type"]["parameters"]["rules"]["values"]]
    assert keys == ["job", "company", "signal"]
    assert [targets("Route by record type", i) for i in range(3)] == [{"Job change row"}, {"Board read?"},
                                                                      {"Alert-worthy signals"}]
    assert targets("Board read?", 0) == {"Account row"} and targets("Board read?", 1) == {"Collect unread boards"}


@pytest.mark.parametrize("sheet,row_node", [("Job changes history", "Job change row"),
                                             ("Accounts snapshot", "Account row"),
                                             ("Signals history", "Signal row")])
def test_sheets_upsert_on_a_key_the_row_carries(sheet, row_node):
    p = NODES[sheet]["parameters"]
    assert p["operation"] == "appendOrUpdate"
    key = p["columns"]["matchingColumns"]
    assert len(key) == 1
    assert key[0] in {a["name"] for a in NODES[row_node]["parameters"]["assignments"]["assignments"]}
    assert targets(row_node, 0) == {sheet}


def test_job_row_from_real_record_shape():
    row = set_row("Job change row", JOB_NEW)
    assert row["eventId"] == "ashby|openai|f9818cd7|new|2026-11-26"      # same day rerun → same row
    assert row["company"] == "openai"                                      # Ashby gives no company name
    assert row["locations"] == "Paris, France" and row["changedFields"] == ""
    assert set_row("Job change row", JOB_CHANGED)["changedFields"] == "descriptionHash"


def test_account_row_keeps_top_three_departments():
    row = set_row("Account row", COMPANY_OK)
    assert row["companyKey"] == "greenhouse:stripe" and row["openJobs"] == 772
    assert row["topDepartments"] == "Account Executives (EMEA) (53), Product Design (14), Security Analytics (13)"


def test_board_check_and_unread_warning():
    cond = NODES["Board read?"]["parameters"]["conditions"]["conditions"][0]
    assert eval_expr(cond["leftValue"], COMPANY_OK) == "ok" and eval_expr(cond["leftValue"], COMPANY_ERR) != "ok"
    out = run_code("Collect unread boards", [COMPANY_ERR])
    assert out[0]["json"]["text"] == "Job boards not read this run (retried next run): gone (lever: board_not_found)"
    assert run_code("Collect unread boards", []) == []


def test_signal_filter_uses_configured_types_and_confidence():
    expr = NODES["Alert-worthy signals"]["parameters"]["conditions"]["conditions"][0]["leftValue"]
    assert eval_expr(expr, SIG_KEEP) is True
    assert eval_expr(expr, SIG_LOW) is False                               # below minConfidence
    assert eval_expr(expr, SIG_TREND) is False                             # not alert-worthy by default
    row = set_row("Signal row", SIG_KEEP)
    assert row["exampleRoles"] == "RevOps Manager; RevOps Analyst"
    assert row["eventId"] == "greenhouse|stripe|new_department|2026-11-26T07:50:35Z"


def test_digest_groups_new_roles_and_selected_signals_by_account():
    records = [JOB_NEW, JOB_REOPENED, JOB_CHANGED, COMPANY_OK, COMPANY_ERR, SIG_KEEP, SIG_LOW, SIG_TREND]
    text = run_code("Build account digest", records)[0]["json"]["text"]
    assert text.splitlines() == [
        "*Hiring changes at your accounts*",
        "• *openai*: 2 new roles: Applied AI Architect, Large Enterprise; Solutions Engineer (reopened)",
        "• *Stripe*: Signal: First open role in department 'Revenue Operations'",
    ]                                                                      # accounts sorted case-insensitively
    assert "Applied Data Researcher" not in text                           # description-only edits are not news


@pytest.mark.parametrize("records", [[], [JOB_CHANGED, COMPANY_OK], [SIG_TREND, SIG_LOW]], ids=["empty", "no-news", "filtered"])
def test_digest_posts_nothing_without_news(records):
    assert run_code("Build account digest", records) == []


def test_failure_alert_and_slack_bodies_are_json_safe():
    for name in ("Post digest to Slack", "Warn about unread boards", "Alert: run failed"):
        p = NODES[name]["parameters"]
        assert p["specifyBody"] == "json" and p["jsonBody"].startswith("={{ JSON.stringify(")
    body = eval_expr(NODES["Alert: run failed"]["parameters"]["jsonBody"], {"error": {"message": 'bad "token"\n'}})
    assert json.loads(body)["text"].startswith('ATS Job Changes Feed run failed: bad "token"')
    title = {"text": 'Engineer "AI"\nPlatform'}
    assert json.loads(eval_expr(NODES["Post digest to Slack"]["parameters"]["jsonBody"], title))["text"] == title["text"]


def test_ships_placeholders_only():
    assert "REPLACE_WITH_YOUR_SHEET_ID" in CONFIG["spreadsheetUrl"]
    assert CONFIG["slackWebhookUrl"].endswith("REPLACE/WITH/YOUR_WEBHOOK")
    assert all("credentials" not in n for n in WF["nodes"])
    assert not WF["pinData"]
