"""Offline tests for greenhouse_snapshot_diff.py (no network). Built by AGI Tools Team."""
import json

import pytest

import greenhouse_snapshot_diff as sd


def board(*jobs, total=True):
    payload = {"jobs": [{"id": i, "title": t, "updated_at": u, "location": {"name": loc},
                         "absolute_url": f"https://example.test/jobs/{i}"} for i, t, u, loc in jobs]}
    if total:
        payload["meta"] = {"total": len(jobs)}
    return payload


A = (1, "Account Executive", "2026-11-01T00:00:00Z", "Berlin")
B = (2, "Data Engineer", "2026-11-01T00:00:00Z", "Remote")


def run(previous, payload):
    return sd.diff(previous, sd.parse_board(payload))


def test_first_run_only_seeds_the_baseline():
    changes, state = run({}, board(A, B))
    assert changes == []
    assert set(state["jobs"]) == {"1", "2"}
    assert state["seeded"] is True


def test_new_job_is_reported_after_the_baseline():
    _, state = run({}, board(A))
    changes, state = run(state, board(A, B))
    assert [(c["changeType"], c["jobId"]) for c in changes] == [("new", "2")]


def test_updated_at_alone_is_not_a_change():
    _, state = run({}, board(A))
    touched = (1, "Account Executive", "2026-11-25T09:00:00Z", "Berlin")
    changes, _ = run(state, board(touched))
    assert changes == []


def test_changed_fields_are_named():
    _, state = run({}, board(A))
    edited = (1, "Senior Account Executive", "2026-11-25T09:00:00Z", "Berlin")
    changes, _ = run(state, board(edited))
    assert len(changes) == 1 and changes[0]["changeType"] == "changed"
    assert changes[0]["changedFields"] == ["title"]


def test_job_is_closed_only_after_two_consecutive_complete_reads():
    _, state = run({}, board(A, B))
    changes, state = run(state, board(A))
    assert changes == [] and state["missing"] == {"2": 1}
    changes, state = run(state, board(A))
    assert [(c["changeType"], c["jobId"]) for c in changes] == [("closed", "2")]
    assert "2" not in state["jobs"]


def test_a_job_that_comes_back_resets_the_miss_counter():
    _, state = run({}, board(A, B))
    _, state = run(state, board(A))
    changes, state = run(state, board(A, B))
    assert changes == [] and state["missing"] == {}


def test_an_emptied_board_needs_an_extra_confirming_read():
    _, state = run({}, board(A, B))
    for _ in range(2):
        changes, state = run(state, board(total=True))
        assert changes == []
    changes, state = run(state, board())
    assert sorted(c["jobId"] for c in changes) == ["1", "2"]
    assert all(c["changeType"] == "closed" for c in changes)


@pytest.mark.parametrize("payload", [
    {"error": "not found"},
    {"jobs": "nope"},
    {"jobs": [{"id": 1}]},                                    # no title
    {"jobs": [{"title": "No id"}]},                           # no id
    {"jobs": [{"id": 1, "title": "x"}], "meta": {"total": 3}},  # partial answer
])
def test_malformed_or_partial_answers_are_rejected(payload):
    with pytest.raises(sd.IncompleteRead):
        sd.parse_board(payload)


def test_a_rejected_read_leaves_the_snapshot_untouched(tmp_path, capsys):
    state_file = tmp_path / "s.json"
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(board(A, B)))
    assert sd.main(["acme", "--state", str(state_file), "--from-file", str(ok)]) == 0
    before = state_file.read_text()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"jobs": [{"id": 1, "title": "x"}], "meta": {"total": 9}}))
    assert sd.main(["acme", "--state", str(state_file), "--from-file", str(bad)]) == 2
    assert state_file.read_text() == before
    assert "incomplete read" in capsys.readouterr().err


def test_cli_prints_json_lines_and_persists(tmp_path, capsys):
    state_file = tmp_path / "s.json"
    first = tmp_path / "1.json"
    second = tmp_path / "2.json"
    first.write_text(json.dumps(board(A)))
    second.write_text(json.dumps(board(A, B)))
    sd.main(["acme", "--state", str(state_file), "--from-file", str(first)])
    assert capsys.readouterr().out == ""
    sd.main(["acme", "--state", str(state_file), "--from-file", str(second)])
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert [(x["changeType"], x["jobId"]) for x in lines] == [("new", "2")]


def test_diff_does_not_mutate_its_input():
    _, state = run({}, board(A, B))
    snapshot = json.dumps(state, sort_keys=True)
    sd.diff(state, sd.parse_board(board(A)))
    assert json.dumps(state, sort_keys=True) == snapshot
