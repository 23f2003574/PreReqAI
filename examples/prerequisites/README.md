# Prerequisite Explorer example: sample paper

| File | What it is |
| --- | --- |
| `sample-paper.pdf` | A one-page, text-based paper ("Attention Is All You Need", abridged) used by the README quickstart. It analyses offline with no API keys. |
| `study_journey.py` | A runnable end-to-end study journey (analyse with a known concept, read the prerequisite tree, mark a concept studied, print the checklist). Offline, no server needed. |
| `cli_journey.py` | The same journey from the command line alone: save the plan, tick a finished concept in `plan.md`, then `--resume` it and `ask` from that progress. Offline, no server needed. |
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

The reply has `status: "success"` and a `responses` list; `responses[0]` holds the `answer` plus the paper's matching concepts and sections
(`supporting_concepts`, `supporting_sections`). To print just the answer, pipe the reply to
`python -c "import sys, json; print(json.load(sys.stdin)['responses'][0]['answer'])"`. No tutoring model is configured in this release, so the `answer` is the built-in definition of the concept
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
Separate several names with commas (`--studied "Probability,Calculus"`) or repeat the flag. Add `--resources` to `analyze` to list a
course or article link for each concept still to study, in study order; over HTTP, `GET /api/session/$SID` returns the same list as `next_resources`.
A name that is not in the study plan is reported in `warnings` (CLI/upload) or answered with HTTP 422 (the `studied` endpoint).

## Keep your study plan

Save the plan as a Markdown checklist (studied concepts ticked, with a study link each) to read or print:

```bash
python -m backend.cli prerequisites analyze examples/prerequisites/sample-paper.pdf --studied Probability --plan-file plan.md
curl -s http://127.0.0.1:8000/api/session/$SID/plan   # the same checklist over HTTP, as text/markdown
```

A misspelt `--known` / `--studied` name is ignored with a warning that suggests the nearest concept ("did you mean 'Probability'?").

## Resume from the command line

The CLI keeps no state between runs; the saved plan is the state. Tick a finished concept in `plan.md` (`- [ ] 1. Linear Algebra` becomes `- [x] 1. Linear Algebra`), then:

```bash
python -m backend.cli prerequisites analyze examples/prerequisites/sample-paper.pdf --known Calculus --resume plan.md --plan-file plan.md
python -m backend.cli prerequisites ask examples/prerequisites/sample-paper.pdf "What should I learn first?" --known Calculus --resume plan.md
python examples/prerequisites/cli_journey.py   # the whole sequence, offline, in a temporary folder
```

The summary then shows `1. Linear Algebra (12h, studied)` and `(1/3 concepts ready)` with the hours left. `--resume` restores only ticked concepts; repeat `--known` each run.
`backend/tests/test_prereqai_cli_journey_example.py` runs the script and checks that output.

## Run the whole journey in one command

```bash
python examples/prerequisites/study_journey.py
```

It runs offline against the sample paper and prints, in order: the study plan without Calculus (`Linear Algebra (12h) -> Probability (10h) -> Neural Networks (15h)`),
the Transformer prerequisite tree (Attention, marked `[satisfied]` because the paper covers it, needs Linear Algebra and Probability; Neural Networks), `1/3 concepts ready` after Linear Algebra is
studied, the tree again from `GET /api/session/$SID` with Linear Algebra marked `[studied]`, the next concepts to study, and the Markdown checklist with Linear Algebra ticked. `backend/tests/test_prereqai_study_journey.py` runs it and checks that output.

For the same tree from the command line add `--tree` to `analyze`. A paper that is not a local file can be named directly: `analyze arXiv:1706.03762`, an arXiv URL or a DOI on the command line,
or the `source` form field over HTTP (`curl -F source=arXiv:1706.03762 http://127.0.0.1:8000/api/prerequisites/analyze`; only arXiv links and DOIs are accepted there, never server paths). Those downloads need network access
and are not run by the tests.
