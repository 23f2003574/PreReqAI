# Release checklist

PreReqAI ships as its source tree (no wheel, no package metadata): the release is what `git archive HEAD`
exports. Run from the repository root on Python 3.10+. Last verified on Python 3.13.

1. **Version.** Set `__version__` in `backend/version.py` (the one source for the API and `--version`).
2. **Clean install.** In a fresh virtualenv: `pip install -r requirements.txt` (what users run), then
   `pip install -r requirements-dev.txt` for the test tools (pytest, httpx2).
3. **Release checks** (about 1 minute, offline; must all pass):
   ```bash
   python -m pytest -q backend/tests/test_prereqai_*.py backend/tests/test_prerequisite_endpoint.py
   python -m pytest -q backend/tests/test_api_generation_*.py backend/tests/test_generated_project_*.py
   ```
   These include the `git archive HEAD` check (`test_prereqai_release_artifact.py`), so commit everything first.
   Run from the repository root (`pytest.ini` puts it on the import path, so bare `pytest` works too).
4. **Primary path.**
   ```bash
   python -m backend.cli --version
   python -m backend.cli prerequisites analyze examples/prerequisites/sample-paper.pdf   # exit 0, "Analysed '...'"
   uvicorn backend.main:app --port 8000   # then the curl commands in examples/prerequisites/README.md
   ```
5. **Docs.** `README.md` quickstart, exit codes and HTTP section still match what step 4 printed.

## Last verified (release candidate, 2026-10-09)

- Fresh virtualenv, `pip install -r requirements-dev.txt`: resolves cleanly.
- Primary path from that environment: `--version` -> `PreReqAI 0.1.0`; the sample-paper analysis exits 0; a running
  `uvicorn` accepts the upload, opens a session and answers a question (topic matched case-insensitively).
- Full `python -m pytest backend/tests`: 11,909 passed, 2 skipped, 47 failed; one (the CLI help usage line, after adding `--version`) was fixed
  afterwards, leaving 46. None are in the release checks above: 44 in `test_research_workspace_*` / `test_consumer_projection_*`, plus the two network tests
  (`test_arxiv_resolver`, `test_research_metadata_resolver`) that need internet access.
- Working tree clean; `cache/` is git-ignored; the only credential-shaped strings are fake test fixtures.

## Rehearsal (2026-10-10, after the day 1-12 product work)

- Fresh virtualenv, `pip install -r requirements-dev.txt`: clean; no undocumented manual step was needed.
- Release checks (step 3): 245 passed (PreReqAI + endpoint) and 235 passed (API generation); includes `git archive HEAD`.
- Primary path (step 4): `--version` -> `PreReqAI 0.1.0`; sample analysis exits 0 and prints the plan, readiness line and time.
  Against a running `uvicorn`: upload with `known=Linear Algebra` -> plan without it; `POST .../sessions/{id}/studied?concept=Probability`
  -> readiness 50%; `GET /api/session/{id}` shows the same progress; a question is answered; a missing upload is HTTP 422.
- Not verified: an actual published paper (the sandbox has no internet; only generated PDFs were used) and session persistence
  (sessions are in memory by design; progress across runs uses `--studied`).

## Completion baseline (2026-10-10)

Verified: release checks 480 passed; full `python -m pytest backend/tests`: 11,928 passed, 2 skipped, 46 failed (the same 44
workspace/projection failures plus the 2 network tests listed below, nothing new). Primary path rehearsed above.
**Not claiming release readiness:** the product has only been run on generated PDFs, so real-paper behaviour is unproven.

| Class | Item |
|---|---|
| Blocker before release | Run at least one real published paper (e.g. an arXiv PDF) end to end and fix what it exposes. |
| Done | Session persistence: opt-in `PREREQAI_SESSION_DIR` (pickle files; single-process, no locking or expiry/cleanup). Default stays in-memory. Verified with a real `uvicorn` stop/start in `test_prereqai_restart_acceptance.py`. |
| Done (documented) | Tutor answers are a placeholder: stated in the README, and every question response carries a warning. Wiring a real model remains open and needs a provider decision. |
| Required before January | The 44 workspace/projection test failures: scoped in "January scope triage" below. |
| Required before January | Section parser: numbered title-case headings now split; unnumbered or all-caps headings outside the fixed list still fold into the previous section. |
| Optional | Concepts outside the registry (e.g. Calculus) have no rules, resources or explanations. |
| Optional | Unmark a studied concept (HTTP analyze form now accepts `studied`, matching the CLI). |
| Optional | Author extraction now reads a plain name-list line on page one; multi-line, affiliation-interleaved or single-name author blocks still show "Unknown Author". |
| Optional | A scanned PDF now warns that it has no extractable text; there is still no OCR, so such papers cannot be analysed. |

## Known open items (not release gates today)

- The 44 non-network failures in the full run (`test_research_workspace_*`, `test_consumer_projection_*`) are real
  bugs in those modules (e.g. a missing `ResearchWorkspaceConsumerProjectionDiagnosticsStageHelper`); steps 3 and 4
  are the gate until they are fixed.
- `test_arxiv_resolver.py` needs network access.
- Tutor answers are a placeholder ("A tutoring model has not yet been configured.") until a model is wired in.

## Fresh-environment verification (2026-10-11, after the day 13 work)

From `git archive HEAD` in a new virtualenv with only `pip install -r requirements.txt` (no dev tools): `--version` -> `PreReqAI 0.1.0`;
the CLI analysis with `--known "Linear Algebra"` exits 0 and plans Probability then Neural Networks; a real `uvicorn` accepted the
documented `curl` upload (with `known`), marked `probability` studied (case-insensitive), answered a question (placeholder warning
present) and, with `PREREQAI_SESSION_DIR` set, left one session file. `starlette.testclient` needs the dev requirement `httpx2`, as documented.
Still unverified: a real published paper, and Python versions other than 3.13.

## January scope triage (2026-10-11)

Order of work, most consequential first. Everything the product's documented workflows need is done and tested except item 1.

1. **Real published paper (blocker, needs input).** Run an arXiv PDF end to end (CLI and HTTP), then fix what it exposes. Likely findings:
   headings outside the numbered/fixed list, multi-line author blocks, two-column text order. Dependency: a PDF in the repo or network access;
   the sandbox cannot reach arXiv (proxy 403). Next step: add the PDF under `examples/` (if its licence allows) or run it locally and send the report.
2. **Tutoring model (needs a decision).** The tutor is the rule-based placeholder and is disclosed in the README and every answer's `warnings`.
   Dependency: a provider choice and an API key. Next step: implement a `Tutor` that builds prompts with the existing `TutorPromptBuilder`
   (`backend/tutor/tutor_prompt_builder.py`), selected when a key is configured; keep the placeholder as the offline default.
3. **44 failing tests in `test_research_workspace_*` (24) and `test_consumer_projection_*` (20, 13 of them fingerprinting) — scoped, not in the release path.**
   Counts by file: fingerprinting 13, actions 12, execution_receipt 5, bootstrap 3, projection_context 3, formatter 2, diagnostics 2, and one each in budget,
   freshness, gateway, readiness. Causes seen: tests mutating frozen dataclasses (`enabled`), a descriptor without `.name`, missing helper
   `ResearchWorkspaceConsumerProjectionDiagnosticsStageHelper`, lambdas not accepting `value=`, status `degraded` where `succeeded` is expected.
   They are the unused research-workspace subsystem, but `backend.session` imports it, so the product loads ~1,260 modules (about 1.3 s at start-up).
   Next step: decide per file whether the test or the code is wrong (start with `fingerprinting`, one `_make_policy` fix covers 11), or move the subsystem
   out of the `backend.session` import path and out of the release test target.
4. **Optional, ordered by user impact:** unnumbered-heading detection; unmark a studied concept; OCR for scanned PDFs;
   resources/explanations for concepts outside the registry.

## Release readiness decision (2026-10-11)

**Status: NOT release-ready.** One blocker remains and it is unverified work, not a failing test: PreReqAI has never been run on a real
published paper. Passing tests alone do not change that, because every test input is a generated PDF or the bundled sample.

Evidence at this commit: release checks (PreReqAI, endpoint, API generation, generated project) 492 passed; full `python -m pytest backend/tests`
11,940 passed, 2 skipped, 46 failed (the 44 workspace/projection failures plus the 2 network tests, nothing new); the primary path was run from a
`git archive` in a clean virtualenv (CLI, real `uvicorn` + `curl`, session restart with `PREREQAI_SESSION_DIR`) -- see the sections above.

| Class | Item |
|---|---|
| Release blocker | Run a real published paper end to end (CLI and HTTP) and fix what it exposes. |
| Required before January | Tutoring model (placeholder is disclosed; a model-backed tutor needs a provider decision). |
| Required before January | The 44 workspace/projection test failures (scoped in the triage above). |
| Required before January | Python versions: 3.11 verified (quickstart + 303 PreReqAI tests, 2026-10-11); 3.12 and 3.10 not yet run. Older interpreters are refused with a clear message; all sources parse under the 3.10 grammar. |
| Optional | unnumbered-heading detection, unmark a studied concept, OCR, multi-line authors, concepts outside the registry. |

## Calculus prerequisite (2026-10-12)

Policy Gradient, Actor-Critic, Score Matching and Reverse Process now list Calculus as a prerequisite, with a curated resource (MIT 18.01), a
justification and the existing order/time entries, so RL and diffusion papers get a derivative refresher in the study plan (`--known Calculus` skips it).
Tests: `test_prereqai_calculus_prerequisite.py`; release checks plus API generation checks pass. Unchanged: real-paper blocker, tutor model,
44 workspace failures, Python 3.10/3.12 runs.

## Built-in tutor answers (2026-10-12)

Integration gap closed: `POST /api/session/{id}/question` returned the bare placeholder even when the analysis already held the answer. The rule-based tutor now
answers from `concept_explanations` and `prerequisite_justifications` for concepts named in the question or retrieved for it ("Why do I need calculus?",
"What is policy gradient?"); unrelated questions keep the placeholder. The response `warnings` still disclose that no tutoring model is configured
(wording differs: "built-in definitions" vs "placeholder"). Tests: `test_prereqai_built_in_answers.py`. Still open: a model-backed tutor (provider decision),
the repeated identical response per workflow in `responses`, real-paper blocker, the 44 workspace failures, Python 3.10/3.12.

## Duplicate question responses (2026-10-12)

Defect (reproduced first): one question returned 3 identical entries in `responses` (one per planned workflow). `InteractiveLearningPipeline` now keeps a reply
only if no earlier one has the same answer and supporting concepts/sections, so the response and the stored conversation agree. Test:
`test_identical_workflow_answers_are_returned_once`. Remaining blockers unchanged: real published paper (needs a PDF or network), tutor model provider,
44 workspace failures, Python 3.10/3.12 runs.

## Deep-learning fundamentals (2026-10-12)

Concepts outside the original registry, now detected with aliases, prerequisites, definitions and (for Backpropagation) a graph edge: Gradient Descent (SGD),
Backpropagation (backprop), Convolutional Neural Network (CNN), Batch Normalization (BatchNorm), Dropout. Tests: `test_prereqai_deep_learning_fundamentals.py`.
Visible change: the bundled sample paper genuinely mentions gradient descent and backpropagation, so its quickstart plan is now Linear Algebra -> Probability ->
Calculus -> Neural Networks (4 steps, ~47h) instead of 3 steps (~37h); pinned tests updated. Still outside the registry: optimisers beyond SGD, embeddings,
RNN/LSTM, autoencoders/VAE, GANs. Blockers unchanged: real published paper, tutor model provider, 44 workspace failures, Python 3.10/3.12.

## CLI question workflow (2026-10-12)

`python -m backend.cli prerequisites ask paper.pdf "question" [--json]` closes a workflow gap: questions were only possible over HTTP because CLI sessions end
with the command. It runs the platform analysis, then the same learning pipeline the API uses, prints the answers and the no-model warning, exits 0; a blank
question is exit 2, an unreadable paper exit 1 with a readable message. Tests: `test_prereqai_cli_ask.py` (4). Not covered: `--known`/`--studied`/limit flags on
`ask`, and `--topic`. Blockers unchanged: real published paper, tutor model provider, 44 workspace failures, Python 3.10/3.12.

## Question matching boundary (2026-10-12)

Failure (reproduced first): the built-in tutor matched concept names as substrings of the question, so "Summarize the paragraphs" answered with the Graphs
justification, "improbability" with Probability, and "self-attention" also pulled in Attention. Matching is now whole-word (plural `s`, case, hyphen/space
tolerant) and longest-name-first. Tests: `test_prereqai_question_matching.py` (7; 4 fail without the fix). Remaining blockers unchanged: real published
paper, tutor model provider, 44 workspace failures, Python 3.10/3.12; concept-group gaps (RNN/LSTM, embeddings, VAE/GAN, other optimisers).

## Personalised difficulty (2026-10-12)

Failure (reproduced first): `--known` / the `known` form field rebuilt the plan, time, actions and readiness but left `paper_difficulty` and
`difficulty_explanations` as computed for the unpersonalised paper (e.g. "2 prerequisite concepts require additional study" with an empty plan).
`PreReqAIPlatform._personalize` now re-runs the difficulty engine and its explanation. Tests: `test_prereqai_known_difficulty.py` (3, all fail without the fix).
Open: `--studied` keeps the full plan hours in `study_time` (by design: studied concepts stay in the plan; remaining-hours semantics not decided).
Blockers unchanged: real published paper, tutor model provider, 44 workspace failures, Python 3.10/3.12.

## Typeset PDF text (2026-10-12)

Failure (reproduced first, with a PDF holding real ligature/dash glyphs via DejaVu Sans): "Diffusion (ff ligature) Model", "Q-learning (non-breaking hyphen)" and "Actor-Critic (en dash)" were not
detected, because PDF text keeps ligature glyphs (ff, fi, fl, ffi, ffl) and non-ASCII dashes. `PDFIngestionEngine` now maps ligatures to their letters,
U+2010-2013 to "-" and drops soft hyphens (`clean_pdf_text`). Side effect: an en dash in a page range reads as "-". Tests: `test_prereqai_typeset_text.py`.
This is real-paper-class behaviour verified only on generated PDFs; the real-paper blocker, tutor provider, 44 workspace failures and Python 3.10/3.12 remain.

## Metadata/body text contract (2026-10-12)

Mismatch (reproduced first): `PDFIngestionEngine` cleaned ligatures/dashes in page text, but `DocumentMetadataExtractor` reads the PDF separately, so the report title
read "an ff/ffi-ligature title" (ligature glyphs) while the body concepts were fine. The cleaner now lives in `backend/ingestion/text_cleaning.py` and is
applied to the PDF metadata fields, the first-page title and the author lines too. Test: `test_title_author_and_metadata_use_the_same_cleaned_text_as_the_body`.
Remaining blockers unchanged: real published paper, tutor model provider, 44 workspace failures, Python 3.10/3.12.

## Learner journey acceptance (2026-10-12)

`test_prereqai_learner_journey.py` runs one learner's whole HTTP journey in order: upload with `known` + `studied` -> personalised plan, readiness and difficulty;
listing; a disclosed built-in answer; a corrupt upload mid-journey (400, no new session, existing session untouched); studying the plan to `ready_to_read`; undoing
a step; a known concept rejected as not planned (422); delete and 404s everywhere. It passed on first run (no new defect found). Limitation: in-process
`TestClient`, not a live server (the live-server restart journey is `test_prereqai_restart_acceptance.py`). Blockers unchanged: real published paper, tutor model
provider, 44 workspace failures, Python 3.10/3.12.

## Docs vs behaviour: tutor answers (2026-10-12)

Mismatch (verified first): the README "Current limitation" note and `examples/prerequisites/README.md` still said every answer is the placeholder, but since the
built-in tutor a concept question ("What is attention?", the documented example) returns the concept's definition. Both docs now describe the real behaviour and
the `ask` command; `test_the_documented_question_behaves_as_the_examples_readme_describes` ties the documented example to the actual response. Blockers
unchanged: real published paper, tutor model provider, 44 workspace failures, Python 3.10/3.12.
