"""Offline tests for the Federal Contract Recompete Radar recipe (no network, no token)."""
import csv
import json
from pathlib import Path

import expiring_contracts as ec

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCHEMA = json.loads((ROOT / "schema" / "federal_recompete_radar_input_schema.json").read_text())
TYPES = {"array": list, "boolean": bool, "integer": int, "string": str}


def read(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_example_input_matches_the_actor_input_schema():
    example = json.loads((ROOT / "federal-recompete-radar" / "input.json").read_text())
    for key, value in example.items():
        prop = SCHEMA["properties"][key]                 # an unknown field fails here
        assert isinstance(value, TYPES[prop["type"]])
        assert isinstance(value, bool) == (prop["type"] == "boolean")
        if "minimum" in prop:
            assert value >= prop["minimum"]
        if "maximum" in prop:
            assert value <= prop["maximum"]


def test_first_run_builds_the_pipeline_soonest_first(tmp_path, capsys):
    out = tmp_path / "pipeline.csv"
    assert ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out), "--today", "2026-11-28"]) == 0
    rows = read(out)
    assert len(rows) == 7 and [r["endDate"] for r in rows] == sorted(r["endDate"] for r in rows)
    assert all(r["status"] == "in window" and r["lastChange"] == "new" for r in rows)
    text = capsys.readouterr().out
    assert text.count("NEW  ") == 7 and "not procurement announcements" in text


def test_withheld_names_stay_empty_and_the_uei_is_kept(tmp_path, capsys):
    out = tmp_path / "pipeline.csv"
    ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out), "--today", "2026-11-28"])
    withheld = [r for r in read(out) if not r["incumbent"]]
    assert len(withheld) == 2 and all(r["incumbentUei"] for r in withheld)
    assert "recipient UEI CU11EQG1CTY9" in capsys.readouterr().out


def test_second_run_updates_rows_instead_of_adding_them(tmp_path, capsys):
    out = tmp_path / "pipeline.csv"
    ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out), "--today", "2026-11-28"])
    capsys.readouterr()
    ec.main(["--from-file", str(HERE / "sample_recompete_run2_illustration.json"), "--pipeline", str(out), "--today", "2026-11-28"])
    rows = {r["awardId"]: r for r in read(out)}
    assert len(rows) == 7
    assert rows["91003124F0012"]["endDate"] == "2028-02-06" and "endDate: 2027-02-06 -> 2028-02-06" in rows["91003124F0012"]["lastChange"]
    assert rows["91003123F0001"]["status"] == "left window"
    assert list(rows)[-1] == "91003123F0001"                 # contracts that left the window sink to the bottom
    text = capsys.readouterr().out
    assert "CHANGED  91003124F0012" in text and "LEFT WINDOW  91003123F0001" in text


def test_a_run_without_changes_says_so_and_keeps_the_file(tmp_path, capsys):
    out = tmp_path / "pipeline.csv"
    ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out), "--today", "2026-11-28"])
    before = out.read_text()
    quiet = tmp_path / "quiet.json"
    quiet.write_text(json.dumps([{"recordType": "summary", "delivered": 0, "unchanged": 7}]))
    capsys.readouterr()
    ec.main(["--from-file", str(quiet), "--pipeline", str(out), "--today", "2026-11-28"])
    assert out.read_text() == before and "No new, changed or left-window contracts" in capsys.readouterr().out


def test_contract_whose_end_date_passed_is_no_longer_listed_as_active(tmp_path, capsys):
    """Regression: the Actor sends no record when a contract simply reaches its end date."""
    out = tmp_path / "pipeline.csv"
    ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out), "--today", "2026-11-28"])
    quiet = tmp_path / "quiet.json"
    quiet.write_text(json.dumps([{"recordType": "summary", "delivered": 0, "unchanged": 5}]))
    capsys.readouterr()
    ec.main(["--from-file", str(quiet), "--pipeline", str(out), "--today", "2026-12-10"])
    rows = read(out)
    by = {r["awardId"]: r for r in rows}
    assert by["91003121F0328"]["status"] == "end date passed"       # ended 2026-12-05
    assert by["91003123F0001"]["status"] == "end date passed"       # ended 2026-12-09
    assert by["91003123F0304"]["status"] == "in window"             # ends 2026-12-14
    assert [r["status"] for r in rows] == ["in window"] * 5 + ["end date passed"] * 2   # active contracts first
    text = capsys.readouterr().out
    assert text.count("END DATE PASSED") == 2 and "No new, changed" not in text
    capsys.readouterr()
    ec.main(["--from-file", str(quiet), "--pipeline", str(out), "--today", "2026-12-11"])
    assert "END DATE PASSED" not in capsys.readouterr().out       # reported once, not on every run


def test_contract_ending_today_is_still_active(tmp_path):
    out = tmp_path / "pipeline.csv"
    ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out), "--today", "2026-12-05"])
    assert {r["awardId"]: r for r in read(out)}["91003121F0328"]["status"] == "in window"


def test_extension_after_the_end_date_passed_brings_the_contract_back(tmp_path):
    out = tmp_path / "pipeline.csv"
    ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out), "--today", "2026-12-10"])
    extended = tmp_path / "extended.json"
    extended.write_text(json.dumps([{"recordType": "contract", "changeType": "changed", "awardId": "91003123F0001",
                                     "endDate": "2027-06-09", "changes": [{"field": "endDate", "before": "2026-12-09",
                                                                           "after": "2027-06-09"}]}]))
    ec.main(["--from-file", str(extended), "--pipeline", str(out), "--today", "2026-12-12"])
    row = {r["awardId"]: r for r in read(out)}["91003123F0001"]
    assert row["status"] == "in window" and row["endDate"] == "2027-06-09"
