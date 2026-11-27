"""Offline checks for the Image Text OCR recipes (no network, no token). Run from the repository root:

    python -m pytest -q tests

Validates each recipe's Actor input against the Actor's input schema (image-text-ocr/schema, copied from Image Text
OCR 0.1.0), each output field a recipe reads against its dataset schema, the structure of the n8n workflow, and the
CSV script with a fixture shaped like real output."""
from __future__ import annotations

import csv
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "image-text-ocr"
PROPS = json.loads((ROOT / "schema/input_schema.json").read_text())["properties"]
OUTPUT_FIELDS = set(json.loads((ROOT / "schema/dataset_schema.json").read_text())["fields"]["properties"])
TYPES = {"array": list, "boolean": bool, "integer": int, "string": str, "object": dict, "number": (int, float)}
SYNC_URL = "https://api.apify.com/v2/acts/agitools~image-text-ocr/run-sync-get-dataset-items"
MCP_URL = "https://mcp.apify.com?tools=agitools/image-text-ocr"

spec = importlib.util.spec_from_file_location("ocr_csv", ROOT / "python/ocr_dataset_to_csv.py")
ocr_csv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ocr_csv)

RECEIPT = {"recordType": "image", "url": "https://example.com/receipt.png", "status": "ok", "errorCode": None,
           "text": "Corner Bakery\nReceipt 4471\n2 x Croissant 5.60\nTotal 18.40 EUR", "lineCount": 4, "textUnits": 1,
           "avgConfidence": 0.854, "source": {"datasetId": "abc", "index": 0, "field": "imageUrl"},
           "row": {"title": "Receipt, \"quoted\"", "shop.url": "https://example.com/p/1"}}
BROKEN = {"recordType": "image", "url": "https://example.com/missing.png", "status": "error", "errorCode": "http_404",
          "text": "", "lineCount": 0, "textUnits": 0, "avgConfidence": None, "source": None, "row": None}


def validate_input(inp: dict) -> list[str]:
    errors = []
    for key, value in inp.items():
        spec_ = PROPS.get(key)
        if spec_ is None:
            errors.append(f"unknown input '{key}'")
            continue
        if not isinstance(value, TYPES[spec_["type"]]) or isinstance(value, bool) and spec_["type"] != "boolean":
            errors.append(f"'{key}' must be {spec_['type']}")
            continue
        if "enum" in spec_ and value not in spec_["enum"]:
            errors.append(f"'{key}' not in {spec_['enum']}")
        if spec_["type"] == "integer" and not (spec_.get("minimum", value) <= value <= spec_.get("maximum", value)):
            errors.append(f"'{key}' out of range")
    if bool(inp.get("imageUrls")) == bool(inp.get("datasetId")):
        errors.append("give imageUrls or datasetId")
    return errors


def workflow() -> dict:
    return json.loads((ROOT / "n8n/image-urls-to-text-webhook.json").read_text())


def node(wf: dict, name: str) -> dict:
    return next(n for n in wf["nodes"] if n["name"] == name)


def test_input_validator_rejects_bad_inputs():
    assert validate_input({"imageUrls": ["https://x/a.png"], "maxImages": 0})
    assert validate_input({"imageUrls": ["https://x/a.png"], "minConfidence": 0.5})
    assert validate_input({"imageUrl": "https://x/a.png"})
    assert validate_input({"maxImages": 5})


def test_clay_input_is_valid():
    inp = json.loads((ROOT / "clay/image-url-to-text-input.json").read_text())
    filled = json.loads(json.dumps(inp).replace("{{Image URL}}", "https://example.com/label.jpg"))
    assert validate_input(filled) == []


def test_n8n_workflow_shape():
    wf = workflow()
    names = {n["name"] for n in wf["nodes"]}
    assert len(names) == len(wf["nodes"])
    hook, run, keep, reply = (node(wf, n) for n in ("Image URLs in", "Run Image Text OCR", "Keep result fields", "Return JSON"))
    assert hook["parameters"]["responseMode"] == "responseNode" and reply["type"] == "n8n-nodes-base.respondToWebhook"
    assert run["parameters"]["url"] == SYNC_URL and run["parameters"]["genericAuthType"] == "httpHeaderAuth"
    query = {p["name"]: p["value"] for p in run["parameters"]["queryParameters"]["parameters"]}
    assert 0 < float(query["maxTotalChargeUsd"]) <= 1
    for src, dst in (("Image URLs in", "Run Image Text OCR"), ("Run Image Text OCR", "Keep result fields"),
                     ("Keep result fields", "Return JSON")):
        assert wf["connections"][src]["main"][0][0]["node"] == dst
    assert "Bearer" not in json.dumps(run["parameters"]), "no token in the template"


def test_n8n_body_uses_only_known_inputs():
    body = node(workflow(), "Run Image Text OCR")["parameters"]["jsonBody"]
    keys = re.findall(r"(\w+):", body.split("JSON.stringify(", 1)[1])
    assert set(keys) <= set(PROPS), set(keys) - set(PROPS)
    sample = {"imageUrls": ["https://example.com/a.png"], "maxImages": 20, "minConfidence": "0.5", "includeLines": False}
    assert set(sample) == set(keys) and validate_input(sample) == []


def test_n8n_reads_only_real_output_fields():
    keep = node(workflow(), "Keep result fields")["parameters"]["assignments"]["assignments"]
    read = {m for a in keep for m in re.findall(r"\$json\.(\w+)", a["value"])}
    assert read and read <= OUTPUT_FIELDS, read - OUTPUT_FIELDS


@pytest.mark.parametrize("path,key", [("mcp/cursor-mcp.json", "mcpServers"), ("mcp/vscode-mcp.json", "servers")])
def test_mcp_configs(path, key):
    cfg = json.loads((ROOT / path).read_text())
    assert cfg[key]["image-text-ocr"]["url"] == MCP_URL


def test_build_input():
    assert ocr_csv.build_input(["https://x/a.png"], None, "imageUrl", ["title"], 10) == \
        {"maxImages": 10, "includeLines": False, "imageUrls": ["https://x/a.png"]}
    ds = ocr_csv.build_input([], "abc123", "images.0", ["title", "url"], 100)
    assert ds == {"maxImages": 100, "includeLines": False, "datasetId": "abc123", "imageField": "images.0",
                  "keepFields": ["title", "url"]}
    assert validate_input(ds) == []
    with pytest.raises(ValueError):
        ocr_csv.build_input(["https://x/a.png"], "abc", "imageUrl", [], 1)
    with pytest.raises(ValueError):
        ocr_csv.build_input([], None, "imageUrl", [], 1)


def test_csv_reads_only_real_output_fields():
    assert set(ocr_csv.BASE_COLUMNS) | {"recordType", "row"} <= OUTPUT_FIELDS


def test_csv_from_json(tmp_path):
    items = tmp_path / "items.json"
    items.write_text(json.dumps([RECEIPT, BROKEN]))
    out = tmp_path / "text.csv"
    assert ocr_csv.main(["--from-json", str(items), "--keep", "title,shop.url", "--out", str(out)]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [r["status"] for r in rows] == ["ok", "error"]
    assert rows[0]["title"] == 'Receipt, "quoted"' and rows[0]["shop.url"] == "https://example.com/p/1"
    assert rows[0]["text"].splitlines()[-1] == "Total 18.40 EUR"
    assert rows[1]["errorCode"] == "http_404" and rows[1]["title"] == "" and rows[1]["avgConfidence"] == ""
    assert ocr_csv.summarize(ocr_csv.to_rows([RECEIPT, BROKEN], [])) == \
        "2 images: 1 with text, 0 without text, 1 failed, 0 blocked"


def test_kept_fields_that_collide_with_ocr_columns_are_kept_under_row_prefix(tmp_path):
    # Codex P2 on PR #9: the README's own example (--keep title,url) lost the page URL to the image URL and wrote
    # two "url" columns.
    page = dict(RECEIPT, row={"title": "Bakery", "url": "https://example.com/p/1", "status": "in stock"})
    items = tmp_path / "items.json"
    items.write_text(json.dumps([page, BROKEN]))
    out = tmp_path / "text.csv"
    assert ocr_csv.main(["--from-json", str(items), "--keep", "title,url,status,title", "--out", str(out)]) == 0
    header = next(csv.reader(out.open(encoding="utf-8")))
    assert header == ["title", "row.url", "row.status"] + ocr_csv.BASE_COLUMNS
    assert len(header) == len(set(header))
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows[0]["row.url"] == "https://example.com/p/1" and rows[0]["url"] == "https://example.com/receipt.png"
    assert rows[0]["row.status"] == "in stock" and rows[0]["status"] == "ok"
    assert rows[1]["row.url"] == "" and rows[1]["url"] == "https://example.com/missing.png"


def test_run_field_handles_dict_and_object():
    class Run:
        default_dataset_id = "d1"
    assert ocr_csv.run_field({"defaultDatasetId": "d1"}, "defaultDatasetId", "default_dataset_id") == "d1"
    assert ocr_csv.run_field(Run(), "defaultDatasetId", "default_dataset_id") == "d1"


def test_missing_token_exits_cleanly(monkeypatch, capsys):
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    assert ocr_csv.main(["--url", "https://example.com/a.png"]) == 2
    assert "APIFY_TOKEN" in capsys.readouterr().err
