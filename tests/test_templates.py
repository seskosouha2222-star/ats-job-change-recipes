"""Offline checks for every integration template (no network, no token). Run from the repository root:

    python -m pytest -q tests

Validates each template's Actor input against the Actor's published input schema (schema/input_schema.json, copied
from ATS Job Changes Feed 0.3.5), each referenced output field against its dataset schema, the structure of the n8n
workflows and the Make blueprint, and scans the repository for secrets."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INPUT_SCHEMA = json.loads((ROOT / "schema/input_schema.json").read_text())
DATASET_SCHEMA = json.loads((ROOT / "schema/dataset_schema.json").read_text())
PROPS = INPUT_SCHEMA["properties"]

# Output fields a template may read: the schema's fields, every view field, and the record-level keys the Actor
# documents for company records (company summaries carry their counts in the 'companies' view).
OUTPUT_FIELDS = set(DATASET_SCHEMA["fields"]["properties"])
for view in DATASET_SCHEMA["views"].values():
    OUTPUT_FIELDS |= set(view["transformation"]["fields"])

BOARD_RE = re.compile(r"^(greenhouse|lever|ashby):[A-Za-z0-9._-]+$")
URL_RE = re.compile(r"^https://[^\s]+$")
MONITOR_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
TYPES = {"array": list, "boolean": bool, "integer": int, "string": str, "object": dict}

CLAY_SAMPLE = {"{{Job board}}": "greenhouse:stripe", "{{Monitor ID}}": "clay-stripe-com"}


def validate_input(inp: dict) -> list[str]:
    errors = []
    for req in INPUT_SCHEMA.get("required", []):
        if req not in inp:
            errors.append(f"missing required '{req}'")
    for key, value in inp.items():
        spec = PROPS.get(key)
        if spec is None:
            errors.append(f"unknown input '{key}'")
            continue
        py = TYPES[spec["type"]]
        if not isinstance(value, py) or (py is int and isinstance(value, bool)):
            errors.append(f"'{key}' must be {spec['type']}")
            continue
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"'{key}' not in {spec['enum']}")
        if py is int and ("minimum" in spec and value < spec["minimum"] or "maximum" in spec and value > spec["maximum"]):
            errors.append(f"'{key}' out of range")
        if py is list and not all(isinstance(v, str) and v.strip() for v in value):
            errors.append(f"'{key}' must hold non-empty strings")
    for c in inp.get("companies", []):
        if not (BOARD_RE.match(c) or URL_RE.match(c)):
            errors.append(f"company '{c}' is neither 'ats:board' nor an https URL")
    if "monitorId" in inp and not MONITOR_RE.match(inp["monitorId"]):
        errors.append("monitorId must be 1-40 letters, digits, '-' or '_'")
    return errors


def n8n_workflows():
    return sorted((ROOT / "n8n").glob("*.json"))


def actor_node(wf: dict) -> dict:
    nodes = [n for n in wf["nodes"] if "agitools~ats-jobs-delta" in json.dumps(n.get("parameters", {}))]
    assert len(nodes) == 1, "exactly one node must run the Actor"
    return nodes[0]


def node_eval(js: str) -> str:
    return subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def template_inputs():
    out = []
    for path in n8n_workflows():
        out.append((path.name, json.loads(actor_node(json.loads(path.read_text()))["parameters"]["jsonBody"])))
    bp = json.loads((ROOT / "make/ats-job-changes-to-slack.blueprint.json").read_text())
    out.append(("make blueprint", json.loads(bp["flow"][0]["mapper"]["data"])))
    for path in sorted((ROOT / "clay").glob("*.json")):
        text = path.read_text()
        for k, v in CLAY_SAMPLE.items():
            text = text.replace(k, v)
        out.append((path.name, json.loads(text)))
    return out


@pytest.mark.parametrize("name,inp", template_inputs(), ids=lambda x: x if isinstance(x, str) else "")
def test_template_input_matches_actor_schema(name, inp):
    assert validate_input(inp) == [], name
    assert inp.get("includeDescription") is False, f"{name}: templates skip free-text descriptions"
    assert inp.get("monitorId"), f"{name}: templates keep their own memory"


def test_validator_rejects_what_the_actor_rejects():
    assert "unknown input 'domain'" in validate_input({"companies": ["greenhouse:stripe"], "domain": "stripe.com"})
    assert any("neither" in e for e in validate_input({"companies": ["stripe.com"]}))
    assert any("monitorId" in e for e in validate_input({"companies": ["lever:x"], "monitorId": "clay-a:b"}))
    assert any("missing" in e for e in validate_input({"mode": "changes"}))
    assert any("not in" in e for e in validate_input({"companies": ["lever:x"], "mode": "delta"}))


def referenced_fields(text: str) -> set[str]:
    fields = set(re.findall(r"\$json\.([A-Za-z_]+)", text))          # n8n
    fields |= set(re.findall(r"\{\{\s*2\.([A-Za-z_]+)", text))       # Make (iterator module 2)
    fields |= set(re.findall(r"[(;\s]2\.([A-Za-z_]+)", text))
    fields |= set(re.findall(r"\b[rcjs]\.([A-Za-z_]+)", text))       # Apps Script / Node / Code node
    return fields - {"length", "slice", "map", "join", "name", "jobs", "padEnd", "push"}


@pytest.mark.parametrize("path", [*n8n_workflows(), ROOT / "make/ats-job-changes-to-slack.blueprint.json",
                                  ROOT / "google-sheets/ats-job-changes.gs",
                                  ROOT / "javascript/ats-job-changes.mjs"], ids=lambda p: p.name)
def test_referenced_output_fields_exist(path):
    produced_here = {"text"} if path.name == "weekly-company-hiring-digest.json" else set()   # Code node output
    unknown = referenced_fields(path.read_text()) - OUTPUT_FIELDS - produced_here
    assert not unknown, f"{path.name} reads fields the Actor does not output: {sorted(unknown)}"


@pytest.mark.parametrize("path", n8n_workflows(), ids=lambda p: p.name)
def test_n8n_structure(path):
    wf = json.loads(path.read_text())
    names = [n["name"] for n in wf["nodes"]]
    ids = [n["id"] for n in wf["nodes"]]
    assert len(set(names)) == len(names) and len(set(ids)) == len(ids)
    for src, outs in wf["connections"].items():
        assert src in names
        for branch in outs["main"]:
            for edge in branch:
                assert edge["node"] in names
    connected = set(wf["connections"]) | {e["node"] for o in wf["connections"].values() for b in o["main"] for e in b}
    working = {n["name"] for n in wf["nodes"] if n["type"] != "n8n-nodes-base.stickyNote"}
    assert working <= connected, "every node is wired"
    assert any(n["type"] == "n8n-nodes-base.stickyNote" for n in wf["nodes"]), "setup note present"
    assert all("credentials" not in n for n in wf["nodes"]), "no credential references are shipped"
    run = actor_node(wf)["parameters"]
    qs = {p["name"]: p["value"] for p in run["queryParameters"]["parameters"]}
    assert float(qs["maxTotalChargeUsd"]) > 0, "per-run charge cap"


def test_make_blueprint_structure():
    bp = json.loads((ROOT / "make/ats-job-changes-to-slack.blueprint.json").read_text())
    flow = bp["flow"]
    assert [m["id"] for m in flow] == [1, 2, 3, 4]
    assert flow[0]["module"] == "http:ActionSendData" and "maxTotalChargeUsd=" in flow[0]["mapper"]["url"]
    assert flow[1]["module"] == "builtin:BasicFeeder" and flow[1]["mapper"]["array"] == "{{1.data}}"
    conds = flow[2]["filter"]["conditions"]
    assert {c[1]["b"] for c in conds} == {"new", "reopened"}
    assert flow[0]["mapper"]["headers"][0]["value"] == "Bearer YOUR_APIFY_TOKEN"


def test_make_slack_body_is_json_encoded_by_make():
    """Codex P2 on PR #1: job titles with quotes or line breaks must not be pasted raw into JSON source."""
    flow = json.loads((ROOT / "make/ats-job-changes-to-slack.blueprint.json").read_text())["flow"]
    assert flow[2]["module"] == "json:TransformToJSON"
    body = flow[3]["mapper"]["data"]
    assert body == '{"text": {{3.json}}}'
    assert "{{2." not in body, "no raw record values inside the JSON body"
    # What Make sends for a hostile title: the encoded string keeps the body valid JSON.
    title = 'Engineer "AI" Platform \\ ops\nsecond line'
    assert json.loads('{"text": %s}' % json.dumps(title))["text"] == title


def test_mcp_configs_point_to_one_actor():
    for path in (ROOT / "mcp").glob("*.json"):
        text = path.read_text()
        assert "https://mcp.apify.com?tools=agitools/ats-jobs-delta" in text, path.name
        json.loads(text)


SECRET_PATTERNS = [re.compile(p) for p in (r"apify_api_[A-Za-z0-9]{20,}", r"hooks\.slack\.com/services/T[A-Z0-9]{6,}",
                                           r"Bearer [A-Za-z0-9_\-]{24,}", r"xox[abp]-[A-Za-z0-9-]{10,}")]


def test_no_secrets_in_repository():
    for path in ROOT.rglob("*"):
        if path.is_file() and ".git" not in path.parts and path.suffix in {".json", ".md", ".py", ".gs", ".mjs", ".sql", ".csv", ".yml"}:
            text = path.read_text(errors="ignore")
            for pat in SECRET_PATTERNS:
                assert not pat.search(text), f"possible secret in {path.relative_to(ROOT)}"


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


@needs_node
def test_apps_script_and_node_inputs_match_schema():
    gs = json.loads(node_eval("console.log(JSON.stringify(require('./google-sheets/ats-job-changes.gs').CONFIG.input))"))
    js = json.loads(node_eval("import('./javascript/ats-job-changes.mjs').then(m => "
                              "console.log(JSON.stringify(m.buildInput(['greenhouse:stripe']))))"))
    for inp in (gs, js):
        assert validate_input({k: v for k, v in inp.items() if v != []}) == []


@needs_node
def test_n8n_digest_code_runs_on_sample_records():
    code = json.loads((ROOT / "n8n/weekly-company-hiring-digest.json").read_text())
    js = next(n for n in code["nodes"] if n["type"] == "n8n-nodes-base.code")["parameters"]["jsCode"]
    items = [{"recordType": "company", "status": "ok", "companySlug": "acme", "companyName": "Acme", "openJobs": 12,
              "newJobs": 3, "closedJobs": 1, "topDepartments": [{"name": "Sales", "jobs": 5}]},
             {"recordType": "company", "status": "ok", "companySlug": "stripe", "companyName": "Stripe",
              "openJobs": 771, "newJobs": 771, "changedJobs": 0, "closedJobs": 0, "topDepartments": []},
             {"recordType": "company", "status": "error", "companySlug": "broken"},
             {"recordType": "job", "changeType": "new"}]
    harness = (f"const $input = {{ all: () => {json.dumps(items)}.map(json => ({{ json }})) }};"
               f"const out = (() => {{ {js} }})(); console.log(out[0].json.text);")
    text = node_eval(harness)
    assert "Acme: 12 open, +3 new, 1 closed (top: Sales)" in text
    assert "Stripe: 771 open (first week monitored)" in text     # real first-run record, run 8s9o9TKoDmlJsz4bV
    assert "Not read this week: broken" in text
