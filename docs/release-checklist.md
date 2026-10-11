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
| Required before January | Python versions other than 3.13 (only 3.13 has been verified). |
| Optional | unnumbered-heading detection, unmark a studied concept, OCR, multi-line authors, concepts outside the registry. |
