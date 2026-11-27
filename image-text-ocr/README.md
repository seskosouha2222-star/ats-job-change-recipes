# Image Text OCR recipes

Working examples for [Image Text OCR](https://apify.com/agitools/image-text-ocr) (`agitools/image-text-ocr`), an Apify
Actor that reads the text in images from a list of URLs or from an Apify dataset. It returns the full text, every line
with its confidence and bounding box, and the dataset fields you choose to keep. The OCR models are embedded in the
Actor, so there is no OCR API key and images are processed inside your run.

You run the Actor in your own Apify account with your own token; nothing in this folder needs a secret.

| You want | Recipe | Platform |
|---|---|---|
| An image-to-text endpoint for your app or workflow | [n8n webhook → OCR → JSON](n8n/image-urls-to-text-webhook.json) | n8n |
| Add the text in product, listing or post images to a scraper's dataset | [Python: dataset → CSV](python/ocr_dataset_to_csv.py) | Code |
| Read the text in one image per row of a table | [Clay HTTP API input](clay/image-url-to-text-input.json) | Clay |
| Let an AI assistant read images | [MCP configuration](mcp/) for Cursor and VS Code | MCP |

Sample images to try it on (invented text, no personal data) are in [`samples/image-text-ocr/`](../samples/image-text-ocr/).

## n8n: image-to-text webhook

Import [`n8n/image-urls-to-text-webhook.json`](n8n/image-urls-to-text-webhook.json), select a Header Auth credential
(`Authorization: Bearer <your Apify token>`) in **Run Image Text OCR**, activate the workflow and send:

```bash
curl -X POST "https://<your-n8n>/webhook/image-to-text" \
  -H "Content-Type: application/json" \
  -d '{"imageUrls": ["https://raw.githubusercontent.com/seskosouha2222-star/ats-job-change-recipes/main/samples/image-text-ocr/receipt.png"]}'
```

The response is a JSON array with one object per image: `url`, `status` (`ok`, `no_text`, `blocked` or `error`),
`text`, `lineCount`, `avgConfidence` and `errorCode`. The workflow keeps at most 20 URLs per request and caps each
request at $0.25 with `maxTotalChargeUsd`.

## Python: add image text to a dataset

```bash
pip install "apify-client>=1.9"
export APIFY_TOKEN=...   # Apify Console -> Settings -> API & Integrations
python python/ocr_dataset_to_csv.py --dataset <datasetId> --image-field imageUrl --keep title,url --out text.csv
```

`--image-field` accepts a dot path (`images.0`, `media.url`). The CSV has the kept fields first, then `url` (the image),
`status`, `lineCount`, `avgConfidence`, `text` and `errorCode`. A kept field with the same name as one of these columns
is written as `row.<name>`: with `--keep title,url` the page link is in `row.url` and the image link in `url`. `--max-charge` (default `0.50`) caps the run. Without a token,
`--from-json items.json` converts saved Actor output to the same CSV.

## Clay

Add an **HTTP API** column that calls
`POST https://api.apify.com/v2/acts/agitools~image-text-ocr/run-sync-get-dataset-items?maxTotalChargeUsd=0.05` with
header `Authorization: Bearer <your Apify token>` and the body in
[`clay/image-url-to-text-input.json`](clay/image-url-to-text-input.json), replacing `{{Image URL}}` with your image
column. Map `text` and `status` from the first item of the response.

## MCP

[`mcp/cursor-mcp.json`](mcp/cursor-mcp.json) and [`mcp/vscode-mcp.json`](mcp/vscode-mcp.json) add the Actor as a tool
through the Apify MCP server (`https://mcp.apify.com?tools=agitools/image-text-ocr`). The client signs you in to Apify
the first time it connects.

## Cost

Image Text OCR is pay-per-event: $0.003 for an image with text, counted per started 20 recognized lines; $0.001 for an
image analysed without readable text; images that fail to download, are not images or are blocked are free. Every
recipe sets a maximum charge per run. Check the current prices on the Actor's Store page.

## Tests

`python -m pytest -q tests` (from the repository root) validates every recipe's input against the Actor's input schema
([`schema/`](schema/), copied from version 0.1.0), checks that every output field a recipe reads exists in the dataset
schema, checks the n8n workflow structure, and runs the CSV script on a fixture shaped like real output. No network,
no token.

| Recipe | Tested |
|---|---|
| Python dataset → CSV | Offline (CSV, input, client versions); the Actor call itself is the documented `apify-client` call |
| n8n webhook | Offline against the schemas; end-to-end run in n8n still to do |
| Clay input | Offline against the input schema only |
| MCP configurations | Configuration shape only |

Not affiliated with Apify, n8n, Clay, Cursor or Microsoft. Built by AGI Tools Team.
