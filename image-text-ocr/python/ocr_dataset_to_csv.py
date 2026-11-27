"""Add the text found in images to the rows of an Apify dataset, and save the result as CSV.

Typical use: a scraper run produced product, listing or post rows with an image URL column. This script runs
Image Text OCR (agitools/image-text-ocr) in dataset mode on those rows and writes one CSV row per image with the
fields you chose to keep, the recognized text, the number of lines and the average confidence.

    pip install "apify-client>=1.9"
    export APIFY_TOKEN=...            # Apify Console -> Settings -> API & Integrations
    python ocr_dataset_to_csv.py --dataset <datasetId> --image-field imageUrl --keep title,url --out text.csv

Image URLs only (no dataset):

    python ocr_dataset_to_csv.py --url https://example.com/a.png --url https://example.com/b.jpg --out text.csv

Offline (no token, no network): turn a JSON array of Image Text OCR output rows into the same CSV.

    python ocr_dataset_to_csv.py --from-json items.json --keep title,url --out text.csv

Cost: Image Text OCR is pay-per-event. --max-charge caps what one run can cost (default $0.50). Images that fail to
download, are not images, or are blocked are free.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

ACTOR = "agitools/image-text-ocr"
BASE_COLUMNS = ["url", "status", "lineCount", "avgConfidence", "text", "errorCode"]


def build_input(urls: list[str], dataset: str | None, image_field: str, keep: list[str],
                max_images: int, include_lines: bool = False) -> dict:
    """Actor input for a list of URLs or for one dataset. Exactly one of urls / dataset must be given."""
    if bool(urls) == bool(dataset):
        raise ValueError("give image URLs or a dataset ID, not both")
    inp: dict[str, Any] = {"maxImages": max_images, "includeLines": include_lines}
    if dataset:
        inp.update({"datasetId": dataset, "imageField": image_field})
        if keep:
            inp["keepFields"] = keep
    else:
        inp["imageUrls"] = urls
    return inp


def run_field(run: Any, camel: str, snake: str) -> Any:
    """apify-client 1.x/2.x return a dict, 3.x returns a Run object."""
    return run.get(camel) if isinstance(run, dict) else getattr(run, snake, None)


def run_actor(inp: dict, token: str, max_charge_usd: str) -> list[dict]:
    from apify_client import ApifyClient

    client = ApifyClient(token)
    run = client.actor(ACTOR).call(run_input=inp, max_total_charge_usd=Decimal(max_charge_usd))
    if run is None:
        raise RuntimeError("the run did not finish")
    status = run_field(run, "status", "status")
    if str(getattr(status, "value", status)) != "SUCCEEDED":
        raise RuntimeError(f"run ended with status {status}")
    return list(client.dataset(run_field(run, "defaultDatasetId", "default_dataset_id")).iterate_items())


def to_rows(items: Iterable[dict], keep: list[str]) -> list[dict]:
    """One flat row per image: kept source fields first, then the OCR result. Line breaks stay inside the text cell."""
    rows = []
    for it in items:
        if it.get("recordType", "image") != "image":
            continue
        kept = it.get("row") or {}
        row = {k: kept.get(k) for k in keep}
        for col in BASE_COLUMNS:
            row[col] = it.get(col)
        rows.append(row)
    return rows


def write_csv(rows: list[dict], keep: list[str], out: Path) -> None:
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keep + BASE_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if v is None else v) for k, v in row.items()})


def summarize(rows: list[dict]) -> str:
    by = {s: sum(r["status"] == s for r in rows) for s in ("ok", "no_text", "blocked", "error")}
    return f"{len(rows)} images: {by['ok']} with text, {by['no_text']} without text, {by['error']} failed, {by['blocked']} blocked"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dataset", help="Apify dataset ID whose rows hold image URLs")
    src.add_argument("--url", action="append", help="image URL (repeat for several)")
    src.add_argument("--from-json", type=Path, help="offline: JSON array of Image Text OCR output rows")
    ap.add_argument("--image-field", default="imageUrl", help="dataset field with the image URL (dot path allowed)")
    ap.add_argument("--keep", default="", help="comma-separated dataset fields to copy into the CSV")
    ap.add_argument("--max-images", type=int, default=50)
    ap.add_argument("--max-charge", default="0.50", help="maximum cost of the run in USD")
    ap.add_argument("--out", type=Path, default=Path("image-text.csv"))
    a = ap.parse_args(argv)
    keep = [k.strip() for k in a.keep.split(",") if k.strip()]

    if a.from_json:
        items = json.loads(a.from_json.read_text(encoding="utf-8"))
    else:
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            print("Set APIFY_TOKEN (Apify Console -> Settings -> API & Integrations).", file=sys.stderr)
            return 2
        inp = build_input(a.url or [], a.dataset, a.image_field, keep, a.max_images)
        items = run_actor(inp, token, a.max_charge)

    rows = to_rows(items, keep)
    write_csv(rows, keep, a.out)
    print(f"{summarize(rows)} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
