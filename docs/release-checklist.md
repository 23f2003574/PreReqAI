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

## Known open items (not release gates today)

- The full `python -m pytest backend/tests` run still has failures in unrelated modules (for example
  `test_consumer_projection_execution_receipt.py`, `test_research_workspace_*`); steps 3 and 4 are the gate.
- `test_arxiv_resolver.py` needs network access.
- Tutor answers are a placeholder ("A tutoring model has not yet been configured.") until a model is wired in.
- A PDF with no extractable text analyses "successfully" with zero concepts.
