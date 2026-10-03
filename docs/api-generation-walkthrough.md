# API generation walkthrough

This walkthrough follows the committed example in
[`examples/api-generation/`](../examples/api-generation/). It takes a validated
API documentation draft and turns it into a runnable FastAPI project. Run
every command from the repository root.

## 1. The input: a validated draft

API generation reads one API documentation draft: the fields of
`LLMAPIDocumentationDraft` (`draft_id`, `endpoint`, `summary`, `description`,
`parameters`, `responses`, `examples`, `status`), saved as JSON. Its `status`
must be `VALIDATED`; a `DRAFT` is rejected.

The example's input is
[`examples/api-generation/draft.json`](../examples/api-generation/draft.json).
It documents `loan_quote` from
[`loan_quote.ipynb`](../examples/api-generation/loan_quote.ipynb) as
`POST /loan-quote`, with:
- typed parameters, some with defaults and `min`/`max` limits;
- a nested `applicant` object;
- an optional `list[str]` parameter;
- a typed response;
- one documented example.

## 2. Generate the project

Preview first. A dry run runs every stage but writes nothing:

```bash
python -m backend.cli api-generation generate \
  --draft examples/api-generation/draft.json \
  --output-dir /tmp/loan-quote-api --dry-run
```

Then generate:

```bash
python -m backend.cli api-generation generate \
  --draft examples/api-generation/draft.json \
  --output-dir /tmp/loan-quote-api
```

Other options:
- `--json` prints the result as JSON (`draft_id`, `endpoint`, `output_dir`, `files`, `openapi_path`, `dry_run`).
- `--base-image` and `--port` set the Dockerfile's base image (default `python:3.11-slim`) and listen port (default `8000`).
- `--config FILE` reads the generator's `generation` settings (`project_name`) and the project's `runtime` settings (`base_image`, `port`) from a `prereqai-config.json`, such as the one in a generated project. Edit that file and regenerate with `--config` to change those settings. Explicit flags override the file's values. A file with a missing, unknown or invalid setting is rejected; there is no silent fallback to defaults.
- `--project-name` names the project, for example `--project-name loan-quote`. The app is then generated in the package `loan_quote/` with entrypoint `loan_quote.main:app`, and the same name appears in the manifest, metadata, README and OpenAPI title. The default is the draft's summary as the name, with the package `app/`. A name that can't become a safe Python package is rejected before anything is generated.

The project is validated before anything is written. On failure the command
prints `error: ...` naming the failing stage and exits `1`. Generation is
deterministic: regenerating the same draft into the same directory gives
identical files.

## 3. The generated project

```
/tmp/loan-quote-api/
├── app/
│   ├── __init__.py
│   └── main.py              # the FastAPI app: request/response models and the endpoint
├── openapi.json             # the app's OpenAPI document
├── requirements.txt         # fastapi, pydantic, uvicorn
├── Dockerfile
├── README.md                # endpoint, parameters and run instructions
├── prereqai-config.json     # editable settings: generation.project_name, runtime.base_image/port
├── prereqai-project.json    # generator, contract version and source draft
└── prereqai-manifest.json   # full file inventory
```

The same output is committed, unedited, as
[`examples/api-generation/generated/`](../examples/api-generation/generated/).

Check that a generated project is healthy. This is read-only and launches
nothing. Exit code `0` means healthy:

```bash
python -m backend.cli api-generation check /tmp/loan-quote-api
```

## 4. Inspect the API and its OpenAPI output

- [`generated/app/main.py`](../examples/api-generation/generated/app/main.py)
  holds the generated Pydantic request model (`PostLoanQuoteRequest`, with
  `Field(..., ge=1000, le=50000)` for `amount`), the response model, and the
  endpoint.
- [`generated/openapi.json`](../examples/api-generation/generated/openapi.json)
  is the OpenAPI document, written at generation time. It matches what the
  running app serves at `/openapi.json`. Interactive docs are at `/docs`.

## 5. Run the generated application

Locally, using the entrypoint `app.main:app`:

```bash
cd /tmp/loan-quote-api
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or with Docker:

```bash
docker build -t loan-quote-api /tmp/loan-quote-api
docker run -p 8000:8000 loan-quote-api
```

Call the endpoint with the draft's documented example input:

```bash
curl -s -X POST localhost:8000/loan-quote -H 'Content-Type: application/json' \
  -d '{"amount": 12000, "term_months": 12, "annual_rate": 0.06, "applicant": {"name": "Ada", "credit_score": 720}}'
# {"monthly_payment":1032.8,"approved":true,"applicant_name":"Ada"}
```

What the generated handler does:
- It does not run notebook code.
- If the request matches a documented example exactly, it returns that
  example's output, with the header `X-Execution: documented-example`.
- Any other valid request gets `501 Not Implemented`.
- An invalid request (for example, `amount` below 1000) gets `422`.

## Keeping the example current

`backend/tests/test_api_generation_example.py` regenerates the example
through the CLI. It fails if the output differs from the committed
`generated/` project. If you change the generator's output on purpose,
regenerate the example in the same change:

```bash
python -m backend.cli api-generation generate \
  --draft examples/api-generation/draft.json \
  --output-dir examples/api-generation/generated
```

## Exit codes

`api-generation generate` exits with:

| code | meaning |
|---|---|
| 0 | success (including `--dry-run`) |
| 2 | command-line usage error |
| 3 | invalid input, configuration or output target (fix it and run again) |
| 4 | generation, generated-artifact validation or writing failed |
| 5 | unexpected internal error |

With `--json`, a failed run still prints one JSON summary on stdout and uses the same exit code.
