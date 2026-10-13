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
`supporting_sections`). No tutoring model is configured in this release, so the `answer` is the built-in definition of the concept
asked about (here "Attention: A mechanism that allows a model to focus ..."). A study-plan question such as "What should I learn first?",
"How long will this take?" or "How difficult is it?" is answered from the analysis too. Any other question that names no concept of the
paper gets the placeholder "A tutoring model has not yet been configured." The response carries a matching entry in `warnings`. Sessions are in memory
and end with the server process unless `PREREQAI_SESSION_DIR` is set (see the main README).

## Track your progress

Tell PreReqAI what you already know or have finished, and the plan, readiness and answers follow. From the repository root:

```bash
python -m backend.cli prerequisites analyze examples/prerequisites/sample-paper.pdf --known Calculus --studied "Linear Algebra"
python -m backend.cli prerequisites ask examples/prerequisites/sample-paper.pdf "What should I learn first?" --known Calculus --studied "Linear Algebra"
```

The summary marks studied steps (`(12h, studied)`) and shows the hours left; the answer lists the remaining steps. Over HTTP, send
`known` / `studied` form fields with the upload, then mark more later with
`curl -s -X POST "http://127.0.0.1:8000/api/prerequisites/sessions/$SID/studied?concept=Probability"` (`-X DELETE` undoes it).
A name that is not in the study plan is reported in `warnings` (CLI/upload) or answered with HTTP 422 (the `studied` endpoint).
