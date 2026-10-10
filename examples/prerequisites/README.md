# Prerequisite Explorer example: sample paper

| File | What it is |
| --- | --- |
| `sample-paper.pdf` | A one-page, text-based paper ("Attention Is All You Need", abridged) used by the README quickstart. It analyses offline with no API keys. |
| `make_sample_paper.py` | Rebuilds `sample-paper.pdf` deterministically from the text it contains. |

From the repository root:

```bash
python -m backend.cli prerequisites analyze examples/prerequisites/sample-paper.pdf
python examples/prerequisites/make_sample_paper.py   # rebuild the PDF after editing its text
```

`backend/tests/test_prereqai_quickstart.py` fails if the committed PDF's content (pages, text,
title) drifts from what `make_sample_paper.py` builds, or if the quickstart command stops succeeding on it.

## Next step: open a session and ask a question (HTTP)

The analysis opens a learning session whose `session_id` is in the response. With the server running
(`uvicorn backend.main:app --port 8000`):

```bash
SID=$(curl -s -F "paper=@examples/prerequisites/sample-paper.pdf;type=application/pdf" \
    http://127.0.0.1:8000/api/prerequisites/analyze | python -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
curl -s -X POST http://127.0.0.1:8000/api/session/$SID/question \
    -H 'Content-Type: application/json' -d '{"question": "What is attention?"}'
```

The reply has `status: "success"` and the paper's matching concepts and sections (`supporting_concepts`,
`supporting_sections`). No tutoring model is configured in this release, so each `answer` is the placeholder
"A tutoring model has not yet been configured." Sessions are in memory and end with the server process.
