# API generation example: loan quote

A small, complete reference for PreReqAI's API generation path, from a
validated API documentation draft to a generated FastAPI project. For a
step-by-step guide, see [the walkthrough](../../docs/api-generation-walkthrough.md).

| File | What it is |
| --- | --- |
| `loan_quote.ipynb` | The source notebook: one typed function, `loan_quote`. |
| `draft.json` | The `VALIDATED` API documentation draft describing that function. It is what the notebook analysis → API documentation pipeline produces; it is committed here directly, because that pipeline needs an LLM. |
| `generated/` | The project `prereqai api-generation generate` writes for this draft, unedited. |

The draft exercises the currently supported draft features: a typed
`POST` endpoint with a summary and description, required and defaulted
parameters, `min`/`max` constraints, a nested object parameter, an optional
`list[str]` parameter, a typed response schema, and one documented example.

## Regenerate and check

From the repository root:

```bash
python -m backend.cli api-generation generate --draft examples/api-generation/draft.json --output-dir examples/api-generation/generated
python -m backend.cli api-generation check examples/api-generation/generated
```

Generation is deterministic, so regenerating an unchanged draft leaves
`generated/` byte-for-byte identical. `backend/tests/test_api_generation_example.py`
fails if the generator's output for this draft drifts from the committed project.
If you change the generator on purpose, regenerate `generated/` in the same commit.

## Run the generated API

```bash
cd examples/api-generation/generated
pip install -r requirements.txt
uvicorn app.main:app
```

`POST /loan-quote` validates its input against the generated request model:
for example, an `amount` below 1000 gets a 422. The generated app does not run
notebook code. It returns the draft's documented output, with the header
`X-Execution: documented-example`, when the request body matches a documented
example exactly. Any other valid request gets a 501.

```bash
curl -s -X POST localhost:8000/loan-quote -H 'Content-Type: application/json' \
  -d '{"amount": 12000, "term_months": 12, "annual_rate": 0.06, "applicant": {"name": "Ada", "credit_score": 720}}'
# {"monthly_payment":1032.8,"approved":true,"applicant_name":"Ada"}
```

The OpenAPI schema is in `generated/openapi.json`, and the live app serves it at `/openapi.json`.
