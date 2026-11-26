"""Offline checks for the EU Tender Alerts templates (no network, no token). Run from the repository root:

    python -m pytest -q tests

Validates each template's Actor input against the Actor's published input schema (eu-tender-alerts/schema, copied from
EU Tender Alerts 0.1.1), each output field a template reads against its dataset schema, and the structure of the n8n
workflow and the Make blueprint."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "eu-tender-alerts"
PROPS = json.loads((ROOT / "schema/input_schema.json").read_text())["properties"]
OUTPUT_FIELDS = set(json.loads((ROOT / "schema/dataset_schema.json").read_text())["fields"]["properties"])
TYPES = {"array": list, "boolean": bool, "integer": int, "string": str, "object": dict, "number": (int, float)}
ACTOR_ID = "qRYeOEc5O9BTeLUBH"            # agitools/eu-tender-alerts; Make's Apify app stores the Actor by ID
MONITOR_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
CLAY_SAMPLE = {"{{Buyer name}}": "Ville de Lyon", "{{Company name}}": "Example Systems", "{{Monitor ID}}": "clay-row-1"}


def validate_input(inp: dict) -> list[str]:
    errors = []
    for key, value in inp.items():
        spec = PROPS.get(key)
        if spec is None:
            errors.append(f"unknown input '{key}'")
            continue
        py = TYPES[spec["type"]]
        if not isinstance(value, py) or isinstance(value, bool) and spec["type"] != "boolean":
            errors.append(f"'{key}' must be {spec['type']}")
            continue
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"'{key}' not in {spec['enum']}")
        if spec["type"] == "integer" and ("minimum" in spec and value < spec["minimum"] or "maximum" in spec and value > spec["maximum"]):
            errors.append(f"'{key}' out of range")
        if spec["type"] == "array":
            allowed = spec.get("items", {}).get("enum")
            if not all(isinstance(v, str) and v.strip() for v in value) or allowed and not set(value) <= set(allowed):
                errors.append(f"'{key}' holds a value the Actor does not accept")
    if "monitorId" in inp and not MONITOR_RE.match(inp["monitorId"]):
        errors.append("monitorId must be 1-40 letters, digits, - or _")
    if not any(inp.get(k) for k in ("keywords", "cpvCodes", "countries", "expertQuery")):
        errors.append("a watch needs at least one filter")
    return errors


def n8n_input() -> dict:
    wf = json.loads((ROOT / "n8n/new-tenders-to-slack.json").read_text())
    return json.loads(next(n for n in wf["nodes"] if n["name"] == "Run EU Tender Alerts")["parameters"]["jsonBody"])


def make_input() -> dict:
    bp = json.loads((ROOT / "make/new-tenders-to-slack.blueprint.json").read_text())
    return json.loads(bp["flow"][0]["mapper"]["inputBody" + ACTOR_ID])


def clay_input(name: str) -> dict:
    text = (ROOT / "clay" / name).read_text()
    for token, value in CLAY_SAMPLE.items():
        text = text.replace(token, value)
    assert "{{" not in text, "every Clay column token has a sample value"
    return json.loads(text)


INPUTS = {"n8n": n8n_input, "make": make_input,
          "clay buyer watch": lambda: clay_input("buyer-watch-input.json"),
          "clay competitor awards": lambda: clay_input("competitor-awards-input.json")}


@pytest.mark.parametrize("name", INPUTS)
def test_template_input_matches_actor_schema(name):
    assert validate_input(INPUTS[name]()) == []


def test_validator_rejects_what_the_actor_rejects():
    assert validate_input({"keywords": ["x"], "unknownField": 1})
    assert validate_input({"keywords": ["x"], "noticeKinds": ["contracts"]})
    assert validate_input({"keywords": ["x"], "lookbackDays": 400})
    assert validate_input({"monitorId": "only-an-id"})
    assert validate_input({"keywords": ["x"], "monitorId": "has spaces"})


def test_referenced_output_fields_exist():
    n8n = (ROOT / "n8n/new-tenders-to-slack.json").read_text()
    make = (ROOT / "make/new-tenders-to-slack.blueprint.json").read_text()
    read = set(re.findall(r"\$json\.([A-Za-z]+)", n8n)) | set(re.findall(r"\b2\.([A-Za-z]+)", make))
    read -= {"defaultDatasetId"}
    assert read and read <= OUTPUT_FIELDS, sorted(read - OUTPUT_FIELDS)


def test_n8n_structure():
    wf = json.loads((ROOT / "n8n/new-tenders-to-slack.json").read_text())
    names = [n["name"] for n in wf["nodes"]]
    ids = [n["id"] for n in wf["nodes"]]
    assert len(set(names)) == len(names) and len(set(ids)) == len(ids)
    for src, outs in wf["connections"].items():
        assert src in names and all(e["node"] in names for b in outs["main"] for e in b)
    connected = set(wf["connections"]) | {e["node"] for o in wf["connections"].values() for b in o["main"] for e in b}
    assert {n["name"] for n in wf["nodes"] if n["type"] != "n8n-nodes-base.stickyNote"} <= connected
    assert all("credentials" not in n for n in wf["nodes"]), "no credential references are shipped"
    run = next(n for n in wf["nodes"] if n["name"] == "Run EU Tender Alerts")["parameters"]
    assert run["url"] == "https://api.apify.com/v2/acts/agitools~eu-tender-alerts/run-sync-get-dataset-items"
    qs = {p["name"]: p["value"] for p in run["queryParameters"]["parameters"]}
    assert float(qs["maxTotalChargeUsd"]) > 0, "per-run charge cap"
    slack = next(n for n in wf["nodes"] if n["name"] == "Post to Slack")["parameters"]["url"]
    assert slack == "https://hooks.slack.com/services/REPLACE/WITH/YOUR_WEBHOOK"
    assert n8n_input()["firstRun"] == "baseline", "the first run posts nothing"


def test_make_blueprint_structure():
    bp = json.loads((ROOT / "make/new-tenders-to-slack.blueprint.json").read_text())
    mods = [m["module"] for m in bp["flow"]]
    assert mods == ["apify:runActorNew", "apify:fetchDatasetItems", "json:TransformToJSON", "http:MakeRequest"]
    first = bp["flow"][0]["mapper"]
    assert first["actorId"] == ACTOR_ID and first["runSync"] is True and float(first["maxTotalChargeUsd"]) > 0
    assert bp["flow"][3]["mapper"]["url"] == "https://hooks.slack.com/services/REPLACE/WITH/YOUR_WEBHOOK"
    assert bp["flow"][3]["mapper"]["jsonStringBodyContent"] == '{"text": {{3.json}}}', "Make encodes the message"
    assert "__IMTCONN__" not in json.dumps(bp), "no connection or account data is shipped"
    kinds = {c["b"] for group in bp["flow"][2]["filter"]["conditions"] for c in group}
    assert kinds == {"notice", "new_tender", "tender_update"}


def test_mcp_configs_point_to_one_actor():
    for name in ("cursor-mcp.json", "vscode-mcp.json"):
        text = (ROOT / "mcp" / name).read_text()
        assert text.count("https://mcp.apify.com?tools=agitools/eu-tender-alerts") == 1 and "token" not in text.lower()
