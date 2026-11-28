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
    assert ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out)]) == 0
    rows = read(out)
    assert len(rows) == 7 and [r["endDate"] for r in rows] == sorted(r["endDate"] for r in rows)
    assert all(r["status"] == "in window" and r["lastChange"] == "new" for r in rows)
    text = capsys.readouterr().out
    assert text.count("NEW  ") == 7 and "not procurement announcements" in text


def test_withheld_names_stay_empty_and_the_uei_is_kept(tmp_path, capsys):
    out = tmp_path / "pipeline.csv"
    ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out)])
    withheld = [r for r in read(out) if not r["incumbent"]]
    assert len(withheld) == 2 and all(r["incumbentUei"] for r in withheld)
    assert "recipient UEI CU11EQG1CTY9" in capsys.readouterr().out


def test_second_run_updates_rows_instead_of_adding_them(tmp_path, capsys):
    out = tmp_path / "pipeline.csv"
    ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out)])
    capsys.readouterr()
    ec.main(["--from-file", str(HERE / "sample_recompete_run2_illustration.json"), "--pipeline", str(out)])
    rows = {r["awardId"]: r for r in read(out)}
    assert len(rows) == 7
    assert rows["91003124F0012"]["endDate"] == "2028-02-06" and "endDate: 2027-02-06 -> 2028-02-06" in rows["91003124F0012"]["lastChange"]
    assert rows["91003123F0001"]["status"] == "left window"
    assert list(rows)[-1] == "91003123F0001"                 # contracts that left the window sink to the bottom
    text = capsys.readouterr().out
    assert "CHANGED  91003124F0012" in text and "LEFT WINDOW  91003123F0001" in text


def test_a_run_without_changes_says_so_and_keeps_the_file(tmp_path, capsys):
    out = tmp_path / "pipeline.csv"
    ec.main(["--from-file", str(HERE / "sample_recompete_run1.json"), "--pipeline", str(out)])
    before = out.read_text()
    quiet = tmp_path / "quiet.json"
    quiet.write_text(json.dumps([{"recordType": "summary", "delivered": 0, "unchanged": 7}]))
    capsys.readouterr()
    ec.main(["--from-file", str(quiet), "--pipeline", str(out)])
    assert out.read_text() == before and "No new, changed or left-window contracts" in capsys.readouterr().out
