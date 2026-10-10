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

## Known open items (not release gates today)

- The 44 non-network failures in the full run (`test_research_workspace_*`, `test_consumer_projection_*`) are real
  bugs in those modules (e.g. a missing `ResearchWorkspaceConsumerProjectionDiagnosticsStageHelper`); steps 3 and 4
  are the gate until they are fixed.
- `test_arxiv_resolver.py` needs network access.
- Tutor answers are a placeholder ("A tutoring model has not yet been configured.") until a model is wired in.
- A PDF with no extractable text analyses "successfully" with zero concepts.
