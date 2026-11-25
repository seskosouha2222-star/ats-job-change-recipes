"""Offline tests for the integration recipes (no network, no token). Run: python -m pytest -q"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import feed_to_sqlite
import hiring_signals

HERE = Path(__file__).parent
RUN1 = json.loads((HERE / "sample_run1_baseline.json").read_text())
RUN2 = json.loads((HERE / "sample_run2_changes.json").read_text())


def test_baseline_only_seeds_history():
    signals, state = hiring_signals.compute_signals(RUN1, {})
    assert signals == []
    assert state["greenhouse:acme-analytics"]["departments"] == ["Design", "Engineering", "Sales"]
    assert state["ashby:example-robotics"]["countries"] == ["Germany"]


def test_second_run_raises_expected_signals():
    _, state = hiring_signals.compute_signals(RUN1, {})
    signals, new_state = hiring_signals.compute_signals(RUN2, state)
    kinds = {(s["company"], s["signal"], s["detail"]) for s in signals}
    assert ("greenhouse:acme-analytics", "new_department", "first department: Data") in kinds
    assert ("greenhouse:acme-analytics", "new_country", "first country: United Kingdom") in kinds
    assert ("ashby:example-robotics", "hiring_surge", "6 new roles in one run") in kinds
    # Sales already existed, so the UK sales role is a new country, not a new department
    assert not any(s["detail"] == "first department: Sales" for s in signals)
    assert "Data" in new_state["greenhouse:acme-analytics"]["departments"]


def test_unknown_company_never_signals_on_first_sight():
    signals, state = hiring_signals.compute_signals(RUN2, {})
    assert signals == []
    assert "greenhouse:acme-analytics" in state


def test_slowdown_needs_more_closures_than_openings():
    state = {"lever:x": {"departments": ["Sales"], "countries": ["France"]}}
    closed = [{"recordType": "job", "changeType": "closed", "ats": "lever", "companySlug": "x", "jobId": str(i),
               "title": f"Role {i}", "department": "Sales"} for i in range(5)]
    signals, _ = hiring_signals.compute_signals(closed, state)
    assert [s["signal"] for s in signals] == ["hiring_slowdown"]


def test_changed_posting_is_remembered_but_not_counted_as_new():
    # Regression: an existing posting moved into a new department/country must update the history, so a later new
    # role there is not reported as a first-time signal; the edit itself is never a new role or a surge.
    state = {"lever:x": {"departments": ["Sales"], "countries": ["France"]}}
    base = {"recordType": "job", "ats": "lever", "companySlug": "x"}
    changed = [{**base, "changeType": "changed", "jobId": "1", "title": "Data Lead", "department": "Data",
                "country": "Spain", "changedFields": ["department", "country"]}]
    signals, state = hiring_signals.compute_signals(changed, state, surge_min=1)
    assert signals == []
    assert "Data" in state["lever:x"]["departments"] and "Spain" in state["lever:x"]["countries"]
    new = [{**base, "changeType": "new", "jobId": "2", "title": "Data Analyst", "department": "Data",
            "country": "Spain"}]
    signals, _ = hiring_signals.compute_signals(new, state)
    assert not any(s["signal"] in ("new_department", "new_country") for s in signals)


def test_reopened_role_counts_as_an_opening():
    state = {"lever:x": {"departments": ["Sales"], "countries": ["France"]}}
    reopened = [{"recordType": "job", "changeType": "reopened", "ats": "lever", "companySlug": "x", "jobId": "9",
                 "title": "Legal Counsel", "department": "Legal", "country": "France"}]
    signals, _ = hiring_signals.compute_signals(reopened, state)
    assert [(s["signal"], s["detail"]) for s in signals] == [("new_department", "first department: Legal")]


def test_zapier_recipe_routes_every_change_type():
    text = (HERE.parent / "no-code" / "make-zapier-sheets.md").read_text()
    section = text.split("## Remove expired postings")[1].split("## ")[0]
    for change in ("new", "reopened", "changed", "closed", "unmatched"):
        assert f"`{change}`" in section, change


def test_state_input_is_not_mutated():
    _, state = hiring_signals.compute_signals(RUN1, {})
    snapshot = json.dumps(state, sort_keys=True)
    hiring_signals.compute_signals(RUN2, state)
    assert json.dumps(state, sort_keys=True) == snapshot


def test_cli_offline_writes_csv_and_state(tmp_path):
    state, out = tmp_path / "state.json", tmp_path / "signals.csv"
    for f in ("sample_run1_baseline.json", "sample_run2_changes.json"):
        assert hiring_signals.main(["--from-file", str(HERE / f), "--state", str(state), "--csv", str(out)]) == 0
    rows = out.read_text().splitlines()
    assert rows[0].startswith("company,companyName,signal")
    assert len(rows) == 1 + 3


def test_sqlite_table_mirrors_open_jobs():
    conn = sqlite3.connect(":memory:")
    feed_to_sqlite.apply_changes(conn, RUN1)
    counts = feed_to_sqlite.apply_changes(conn, RUN2)
    assert counts["deleted"] == 1 and counts["skipped"] == 2
    ids = {r[0] for r in conn.execute("SELECT job_id FROM open_jobs WHERE company_slug = 'acme-analytics'")}
    assert ids == {"a1", "a2", "a4", "a5"}                       # a3 closed
    title = conn.execute("SELECT title FROM open_jobs WHERE job_id = 'a2'").fetchone()[0]
    assert title == "Senior Backend Engineer"                     # changed record applied
    assert conn.execute("SELECT COUNT(*) FROM open_jobs").fetchone()[0] == 4 + 9


def test_unmatched_deletes_like_closed():
    conn = sqlite3.connect(":memory:")
    feed_to_sqlite.apply_changes(conn, RUN1)
    gone = {**RUN1[0], "changeType": "unmatched", "baseline": False}
    feed_to_sqlite.apply_changes(conn, [gone])
    assert conn.execute("SELECT COUNT(*) FROM open_jobs WHERE job_id = 'a1'").fetchone()[0] == 0


def test_run_field_supports_every_client_version():
    class RunModel:                                   # apify-client 3.x: attributes, snake_case
        status = "SUCCEEDED"
        default_dataset_id = "abc"
    as_dict = {"status": "SUCCEEDED", "defaultDatasetId": "abc"}   # apify-client 1.x / 2.x
    for run in (RunModel(), as_dict):
        assert hiring_signals.run_field(run, "status", "status") == "SUCCEEDED"
        assert hiring_signals.run_field(run, "defaultDatasetId", "default_dataset_id") == "abc"
    assert hiring_signals.run_field(None, "status", "status") is None


def test_n8n_workflow_is_consistent():
    wf = json.loads((HERE.parent / "n8n" / "ats-job-changes-to-slack.json").read_text())
    names = [n["name"] for n in wf["nodes"]]
    assert len(names) == len(set(names))
    for src, outputs in wf["connections"].items():
        assert src in names
        for branch in outputs["main"]:
            for link in branch:
                assert link["node"] in names
    apify = next(n for n in wf["nodes"] if n["name"] == "Run ATS Job Changes Feed")
    assert "agitools~ats-jobs-delta" in apify["parameters"]["url"]
    body = json.loads(apify["parameters"]["jsonBody"])
    assert body["monitorId"] and body["emitBaseline"] is False
