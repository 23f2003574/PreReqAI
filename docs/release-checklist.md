# Release checklist

PreReqAI ships as its source tree (no wheel, no package metadata): the release is what `git archive HEAD`
exports. Run from the repository root on Python 3.10+. Last verified on Python 3.13.

1. **Version.** Set `__version__` in `backend/version.py` (the one source for the API and `--version`).
2. **Clean install.** In a fresh virtualenv: `pip install -r requirements.txt` (what users run), then
   `pip install -r requirements-dev.txt` for the test tools (pytest, httpx2).
3. **Release checks** (about 1 minute, offline; must all pass):
   ```bash
   python -m pytest -q -m prereqai   # the PreReqAI tests only (same files as test_prereqai_*.py + test_prerequisite_endpoint.py); about 3 minutes
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
| Required before January | Section parser: numbered title-case headings and IEEE-style roman-numbered all-caps headings (`II. PROPOSED METHOD`) now split; unnumbered headings outside the fixed list (and roman-numbered title-case ones) still fold into the previous section. |
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
| Required before January | Python versions: 3.11 verified (quickstart + 303 PreReqAI tests, 2026-10-11); 3.12 verified (fresh venv from requirements-dev.txt on Python 3.12.3: the README quickstart analysis, then `pytest -m prereqai` = 534 passed, 11747 deselected, 0 failed, 2026-10-27); 3.10 not yet run (no 3.10 interpreter in the sandbox). Older interpreters are refused with a clear message; all sources parse under the 3.10 grammar. |
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

## References excluded from concept detection (2026-10-12)

Failure (reproduced first): cited titles in the bibliography counted as concepts, so a transformer paper citing GNN, RL and diffusion work got Graphs and Markov Decision
Process study steps. The detector now skips paragraphs of References/Bibliography/Works Cited/Acknowledgements sections (numbered or roman headings too); the section parser
gained Bibliography and Works Cited headings. Tests: `test_prereqai_references_excluded.py` (6; 5 fail without the fix). Limit: a bibliography whose heading the parser
does not recognise is still counted. Unresolved for the next project day: a real published paper has still never been run (needs a PDF or network), the tutor model provider
decision, the 44 workspace/projection failures, Python 3.10/3.12 runs, concept groups (RNN/LSTM, embeddings, VAE/GAN, other optimisers), two-column reading order. NOT release-ready.

## Day 13 record: bounded sessions evict the idlest (2026-10-13)

Defect (found reviewing the memory cap added earlier today): eviction dropped the session created longest ago, so a learner returning to a long-running study session could lose it
before an idle newer one. Eviction now uses the latest create/get time. Test: `test_an_active_old_session_outlives_an_idle_newer_one` (fails without the change).
Today's other changes (all separate commits): study-plan answers from the analysis, `ask --known/--studied`, hyphenated line breaks, unsaved-session warning, study actions follow
progress, progress shown in the CLI summary, `~` in `PREREQAI_SESSION_DIR`, session cap, example README. Full suite: 45 failed, 12,030 passed (arXiv test deselected, network).
Unresolved for the next project day (genuine blockers): a real published paper has still never been run; the tutor model provider decision; the 45 failures (all in the
research-workspace / consumer-projection subsystems and the network resolver tests, none in the release checks); Python 3.10/3.12 runs; the API `study_time` still describes the whole plan after
progress; a failed save after analysis (studied/question) is still silent; concept groups (RNN/LSTM, embeddings, VAE/GAN) and two-column reading order. NOT release-ready.

## Day 13 hand-off (2026-10-15)

Release checks (step 3, PreReqAI + endpoint tests) were green at commit 11 (367 passed) and again at the day-13 commit (370 passed). Done today: `analyze --resources` and the
session `next_resources` list (study order), whitespace- and comma-tolerant `known`/`studied` on every surface, unreadable saved
sessions explained and clearable, one failure envelope for the studied endpoints, prerequisite definitions in answers, no
`cache/` written for local PDFs, upload errors name the uploaded file, example walkthrough corrected.

Still open for the next session:

| Class | Item |
|---|---|
| Blocker before release | Run a real published paper end to end (the sandbox has no internet; only generated PDFs so far). |
| Blocker before release | The tutor is a placeholder: wiring a model needs a provider decision. |
| Required before January | The 44 `test_research_workspace_*` / `test_consumer_projection_*` failures, plus the two network tests. |
| Required before January | Detector coverage: only 7 prerequisite concepts and 8 curated resources; e.g. diffusion papers get no variational-inference or KL-divergence prerequisites. |
| Optional | CLI keeps no state between runs (progress is re-sent with `--studied`); `python -m backend.cli` only works from the repository root. |
| Optional | The resource library has one entry per concept and no alternatives or difficulty levels. |

## Python 3.12 verification (2026-10-27)

Fresh `python3.12 -m venv`, `pip install -r requirements-dev.txt`, README quickstart (`python -m backend.cli prerequisites analyze examples/prerequisites/sample-paper.pdf`, exit 0, 5 concepts, 4 missing), then `python -m pytest backend/tests -m prereqai`: **534 passed, 11747 deselected, 0 failed** in 350 s. Not run: the full suite on 3.12, and any run on 3.10. Remaining version blocker: Python 3.10.

## Workspace/projection test failures resolved (2026-10-27)

`pytest backend/tests -k "research_workspace or consumer_projection"`: **4112 passed, 0 failed** (from 31 failed at the start of the day). One product defect (the workspace action projector read `descriptor.name`, which capability descriptors do not have, so capability gating crashed) and one formatting mismatch (receipt fingerprints are shortened to 8 characters like the comparator) were fixed in code; the rest were stale test doubles (renamed enum members, a nonexistent stage helper, a keyword name, `name`/`enabled` assumptions about frozen capability descriptors). The "44 workspace failures" item above is therefore closed. Still open: the two network tests (`test_arxiv_download`, the metadata resolver), the real-paper blocker, the tutor model, Python 3.10. Not run: the complete suite after these fixes.

## Sequence models and the Adam optimiser (2026-10-28)

Recurrent Neural Network (aliases RNN, LSTM, GRU, long short-term memory) and Adam Optimizer (AdamW; the bare word "Adam" is deliberately not an alias, it is a common surname) are now
detected, with definitions and prerequisites (Neural Networks, Calculus; Adam also Probability). The bundled sample paper genuinely says "Recurrent neural networks", so its analysis now reports
6 concepts instead of 5; the study plan is unchanged (4 steps, ~47h). Pinned tests updated accordingly; new tests: `test_prereqai_sequence_models_and_optimisers.py`. Still outside the registry:
variational inference / VAE, GANs, embeddings, optimisers other than Adam.

## Release readiness status (2026-10-27)

**Status: still NOT release-ready.** One blocker remains and it is unverified work, not a failing test: PreReqAI has not been run on a real published paper (the sandbox has no route to arXiv; `test_arxiv_download` and `test_crossref_lookup` fail on `ProxyError` here). Passing tests alone do not change that.

Evidence at commit `8413def` (verified):

| Check | Result |
|---|---|
| Full suite, `python -m pytest backend/tests` (local, Python 3.13, 2026-10-27) | **12346 passed, 2 skipped, 2 failed** in 292 s; the 2 failures are the two network tests above |
| `pytest -m prereqai` | 602 passed, 0 failed |
| GitHub Actions "PreReqAI checks" (`.github/workflows/prereqai.yml`: `pytest -m prereqai` + the README quickstart on **Python 3.10 and 3.13**) | green on every push from 468cbe5 to 8413def (runs 10 to 16); the 3.10 job passed from run 2 on, the first 3.13 failure (PyMuPDF 2.x printing onnxruntime warnings to stderr) is fixed by `PyMuPDF>=1.26.0,<2` |

Changes to the table in "Release readiness decision": the **Python 3.10** item is closed by the CI job above (it installs `requirements-dev.txt` and runs the release checks on a real 3.10 interpreter; 3.11 and 3.12 were verified earlier in fresh environments). The **workspace/projection failures** item is closed (see the 2026-10-27 section above). CI covers Linux only.

Still open, in priority order:

1. **Release blocker:** run one real published paper end to end (CLI and HTTP) with network access and fix what it exposes.
2. **Required before January:** a model-backed tutor (provider decision); the rule-based tutor discloses that it is a placeholder for free-form questions.
3. **Required before January:** broader detector coverage. Information Theory (entropy, KL divergence) is now a prerequisite of Diffusion Model, Score Matching and Reverse Process (2026-10-27); other gaps remain (for example variational inference, optimisation beyond gradient descent, sequence models).
4. **Optional:** OCR for scanned PDFs, author-year bibliographies, concepts outside the registry, a dependency lockfile, Windows and macOS CI.

## CI regression found and fixed (2026-10-28)

GitHub Actions "PreReqAI checks" was red on `261240a`, `2f88ca5` and `1d4f1c0` (runs 25 to 27, both Python 3.10 and 3.13): the blank-paper usage error added in `261240a` contradicted the
established contract in `test_prereqai_configuration_surface.py` (an empty path is a structured analysis failure, exit 1, the same shape as the API). Those commits were checked locally with a
`-k` subset that did not select that test; the full `pytest -m prereqai` run found it (1 failed, 628 passed). The blank-paper validation and its test were removed; the contract test passes again.
Lesson recorded: run the full `pytest -m prereqai` (about 3 minutes) before pushing, not a `-k` subset. Open: remaining-hours semantics are now decided (`study_time.remaining_hours`, added 2026-10-28);
the real-paper blocker, tutor model provider and the items above are unchanged.

## Variational inference detection (2026-10-29)

Gap (from "Still open" item 3 above, which named variational inference): no concept for it existed, so papers using the ELBO got no definition or prerequisites for it. Added "Variational Inference"
(aliases ELBO, evidence lower bound, variational lower/bound) with prerequisites Probability, Information Theory and Calculus, and a definition. Test: `test_prereqai_variational_inference.py` (3, incl. an unrelated
"variational principle" paper that must not match). `pytest -m prereqai`: 631 passed, 0 failed. Still open: other detector gaps (for example VAEs/generative models beyond diffusion), and the items above.

## Plural acronym aliases were not counted (2026-10-29)

Defect: `RuleBasedConceptDetector` matched a plural only for a concept's name, so "GRUs", "DDPMs", "MHAs", "SGDs" and "ELBOs" were missed ("RNNs, GRUs and LSTMs" counted 2 of 3 mentions; "DDPMs" detected nothing). Fix: aliases match a plural too,
and an alias whose plural is also listed ("RNN"/"RNNs") is deduplicated so it is not double counted. Test: `test_prereqai_plural_aliases.py` (3; 2 fail without the fix). `pytest -m prereqai`: 634 passed, 0 failed.

## Quiz step added to the tutor (2026-10-29)

Gap: the README promises adaptive quizzes, but `QuizGenerator`/`QUIZ_BANK` were not reachable from `ask` or the HTTP question route, so a learner could not self-test after studying. `RuleBasedTutor` now answers "Quiz me"
/ "Quiz me on Softmax" with the concept's questions and answers (no concept named: the paper's concepts that have questions; a concept without questions says so). Test: `test_prereqai_tutor_quiz.py` (3). `pytest -m prereqai`: 637 passed, 0 failed.
Limitation: only Attention, Transformer and Softmax have questions; answers are shown with the questions, not graded.

## Resumed plans survive reformatting (2026-10-29)

Risk: `--resume` / the `resume` upload restored progress only from lines starting exactly `- [x] N. Name (~Nh)`. A plan re-saved by a Markdown formatter or editor (`*` or `+` bullets, indented lines) silently restored no studied concepts
(reproduced: a `*`-bullet copy of a plan with Probability ticked resumed with 0/3 ready, no warning), so progress was lost. The ticked-item and "Already known" patterns in `study_plan_markdown.py` now accept `-`, `*`, `+` bullets and leading indentation
(CRLF and BOM already worked). Test: `test_prereqai_plan_resume_reformatted.py` (3; 1 fails without the fix). `pytest -m prereqai`: 640 passed, 0 failed. Limitation: ordered-list renumbering and edited step text are still not recognised.

## Damaged cached downloads are replaced (2026-10-29)

Failure: `ArxivResolver`/`DoiResolver` reused any file already in `cache/arxiv` or `cache/doi` (`pdf_path.exists()`). New downloads are validated and stored atomically, but an empty or HTML file left by an older version or an interrupted
write was returned forever, so every `analyze arXiv:...` failed until the learner found and deleted the cache by hand. A cached file that does not start with `%PDF` is now removed and downloaded again; a good cached PDF is still reused with no request.
Test: `test_prereqai_cached_download_recovery.py` (3; 2 fail without the fix). `pytest -m prereqai`: 643 passed, 0 failed. Limitation: a truncated file that still starts with `%PDF` is not detected.

## Quiz honours the question topic (2026-10-29)

Mismatch: the session's `topic` (HTTP `topic` field, `ask --topic`) is stored as the session's active concept and scopes the other answers, but the quiz step added earlier ignored it: `ask "Quiz me" --topic Softmax` quizzed every paper concept.
`RuleBasedTutor._quiz_answer` now uses the session's active concept (a concept without questions says so); a concept named in the question still wins. Test: `test_prereqai_tutor_quiz.py::test_a_topic_scopes_the_quiz_over_http_and_the_cli_alike` (HTTP and CLI give the same answers).
Limitation: the active concept stays set for later questions in the same HTTP session, as for every topic-scoped answer.

## arXiv identifier shape is validated (2026-10-29)

Gap: the new-style arXiv pattern was `[0-9]+\.[0-9]+`, so a typo such as `arXiv:1706.037` or `arXiv:1.1` passed source detection and triggered a network download that could only fail (or fetch a different paper). Identifiers are now
`YYMM.NNNN` / `YYMM.NNNNN` (plus the existing old-style form); anything else is rejected up front as an unsupported source. Test: `test_prereqai_arxiv_id_shape.py` (9; 5 fail without the fix). `pytest -m prereqai`: 653 passed, 0 failed.
Checked and already adequate: empty/non-PDF uploads, blank or junk `source`, wrong-typed or oversized questions, bad modes, CLI limits (0, negative, nan, inf), plan/resume paths. Limitation: a well-formed id that does not exist still fails at download.

## Mistyped arXiv/DOI reference gets a useful hint (2026-10-29)

Problem: a mistyped reference (`arXiv:1706.037`, `arXiv:`, `doi:10.1000`) failed with the hint "The paper must be a PDF file (a path ending in .pdf)", which tells someone who typed an arXiv id to do something unrelated. The failure now
shows what a valid reference looks like (`https://arxiv.org/abs/1706.03762`, `arXiv:1706.03762`, `10.1000/xyz123`, `https://doi.org/...`); other unsupported inputs (`notes.txt`, a directory, `my-doi-notes.txt`) keep the PDF hint. This applies to the CLI and
HTTP `source` field alike (shared failure builder; the CLI path is the one tested). Test: `test_prereqai_bad_source_hint.py` (8; 5 fail without the fix). `pytest -m prereqai`: 661 passed, 0 failed.

## Session isolation covered (2026-10-29)

Gap: no test analysed the same paper twice and checked that the sessions are independent, although the server is single-process and every session shares module-level engines (detector, planner, recommender, tutor, session manager).
`test_prereqai_session_isolation.py` (3): studied/known/topic-question changes in one session leave the other's readiness, progress, study time and exported plan untouched; a topic in one session does not scope another's quiz; deleting
one session leaves the other usable. It passed on first run (no defect found). Honest limit: it guards against shared mutable state in general; a mutation that removed the report `deepcopy` in the platform did not fail it, because each analysis builds
its own report. `pytest -m prereqai`: 664 passed, 0 failed.

## Tutor name matching shares one helper (2026-10-29)

Duplication: `rule_based_tutor.py` spelled the same whole-word regex `(?<![a-z0-9])<name>s?(?![a-z0-9])` out in seven places (definitions, prerequisites, study plan, resources, quiz), so a fix to the rule (as when "paragraphs" had to stop matching "Graphs") had to be repeated seven times.
They now call `_name_pattern(name, plural=True)`; the generated patterns are character-for-character the same, so behaviour is unchanged. Test: `test_prereqai_tutor_name_matching.py` (3). `pytest -m prereqai`: 667 passed, 0 failed.
Other regexes in the file (the quiz-request words) are single-use and were left alone.

## Unwritable working directory no longer fails an arXiv/DOI analysis (2026-10-29)

Blocker: downloads are cached in `cache/arxiv` / `cache/doi` relative to the current directory. When that directory cannot be written (a read-only checkout or container, or the server started from an unusual directory), `_store` raised
after the paper had been downloaded successfully, so `analyze arXiv:...` failed with a file-system error. The resolvers now fall back to `<tempdir>/prereqai-cache/<arxiv|doi>` and look in both places before downloading. Defaults are unchanged
when the directory is writable. Reproduced with a cache path under a regular file (a root user is not stopped by chmod, so a real read-only directory was not tried). Test: `test_prereqai_unwritable_cache.py` (2; 1 fails without the fix).
`pytest -m prereqai`: 669 passed, 0 failed. Not tested: Windows/macOS temp locations.

## Generative-model detector coverage (2026-10-29)

Release status check first: the release blocker "run one real published paper end to end" **could not be attempted in this environment** (`analyze arXiv:1706.03762` fails with "the arXiv or DOI server could not be reached": no outbound network), so it remains open and
is not claimed. What could be closed from the "Required before January: broader detector coverage" item: variational autoencoders (VAE) and generative adversarial networks (GAN), the models papers on diffusion/generation compare against, were not recognised
(only the ELBO had been added). Added both concepts with plural handling, definitions and prerequisites (Neural Networks, Probability and Information Theory for VAEs; Neural Networks, Probability and Calculus for GANs). Test:
`test_prereqai_generative_models.py` (3, including look-alike words that must not match). `pytest -m prereqai`: 672 passed, 0 failed. Still open: the real-paper run, a model-backed tutor, large-language-model/attention variants and the optional items above.

## Core vocabulary of the target domains (2026-10-29)

Gap (verified by probing 41 common terms against the detector): the project targets transformer, diffusion, RL and graph ML papers, yet "reinforcement learning" itself, large language models (LLM/BERT/GPT), cross-entropy and maximum likelihood
were not recognised, so an RL or language-model paper did not list its own subject. Added Reinforcement Learning, Large Language Model, Cross-Entropy Loss and Maximum Likelihood Estimation with definitions and prerequisites that all have curated resources.
Test: `test_prereqai_core_ml_vocabulary.py` (3). `pytest -m prereqai`: 675 passed, 0 failed. Still undetected (probed): embeddings, fine-tuning/pretraining, regularisation/overfitting, convolution, autoregressive models, Markov chains, Monte Carlo,
KL divergence/entropy as paper concepts, contrastive/self-supervised learning, distillation, mixture of experts, reward/policy as plain words (deliberately not matched).

## Training and sampling vocabulary (2026-10-30)

Gap (from the "still undetected" list above): overfitting, fine-tuning and Monte Carlo/MCMC were not recognised, so papers on transfer learning or sampling-based inference did not list them. Added the three concepts with aliases, definitions
and prerequisites (Probability, Neural Networks, Calculus, all with curated resources). Test: `test_prereqai_training_vocabulary.py` (3, including look-alike words and a References-section title that must not match).
Still undetected: embeddings, regularisation, convolution, autoregressive models, Markov chains, KL divergence, contrastive/self-supervised learning, distillation, mixture of experts.

## Overfitting / fine-tuning spelling variants (2026-10-30)

Defect (reproduced): the aliases added in the previous entry missed common spellings, so "over-fit", "over-fitted", "fine tune" and "fine tuned" were not detected although "overfitted" and "fine-tuned" were; a paper using them listed neither concept.
Fix: the four spellings were added as aliases. Test: `test_spaced_and_hyphenated_spellings_of_the_same_terms_are_detected` (fails without the fix). Known limit: "fine tuned" is a plain-English phrase too, so a non-ML use ("a fine tuned string") would count.

## Practice questions for more core concepts (2026-10-30)

Gap (verified): only 3 of the 44 registry concepts (Transformer, Attention, Softmax) had quiz questions, so "Quiz me" on a reinforcement learning, diffusion, VAE or overfitting paper answered "no practice questions yet". Added questions with answers for
Backpropagation, Cross-Entropy Loss, Overfitting, Reinforcement Learning, Diffusion Model and Variational Autoencoder. Tests in `test_prereqai_tutor_quiz.py` (2 new, including a concept that still has none and must say so). Still without questions: the other 35 concepts (Gradient Descent is deliberately left as the existing "no questions" case in older tests).

## Failed "mark known" no longer leaves a stale studied note (2026-10-30)

Risk (reproduced): `mark_concept_known` recorded "this concept was studied" in `paper.studied_while_known` before taking its rollback backup, so when the rebuild failed the session was restored *with* the note. Un-studying the concept, marking it known and then undoing that would
wrongly bring it back as studied (readiness and progress overstated). The backup is now taken first. Test: `test_prereqai_failed_known_rollback.py` (2; the failure case fails without the fix, the success case guards the existing undo behaviour).
Limit: only this one rollback path was audited; `unmark_concept_known` already backs up before changing anything.

## arXiv download retries a body cut short mid-download (2026-10-30)

Failure (reproduced with scripted `requests` errors): the bounded retry covered dropped connections and 429/5xx replies only, so a body cut off mid-download (`ChunkedEncodingError`) failed the analysis on the first attempt although a retry normally succeeds.
It is now treated as transient (2 retries, then the original error surfaces, nothing partial cached). A read timeout is deliberately *not* retried: `test_prereqai_retry_safety` requires it to be reported at once as a timeout, and retrying would add minutes. Tests: three in `test_prereqai_arxiv_recovery.py` (the two cut-short ones fail without the fix; the third pins the timeout behaviour).
Not changed: the DOI resolver's publisher download has no retry; `test_arxiv_resolver.py::test_arxiv_download` needs the network and fails in this sandbox before and after.

## Question topic accepts study-plan prerequisites (2026-10-30)

Integration defect (reproduced): the study plan and progress endpoints list prerequisites the paper never names (Probability, Linear Algebra...), but `resolve_topic` (shared by `POST /question` and `prerequisites ask --topic`) only accepted concepts detected in the paper, so a learner could study Probability yet got "Unknown topic: 'Probability'" when focusing a question or quiz on it, although the tutor pipeline handles such a topic (`Quiz me` -> "no practice questions yet for Probability").
`resolve_topic` now also accepts the session's study-progress concepts (case-insensitive); the 422 hint lists both. A concept marked known leaves the plan and is rejected again. Tests: `test_prereqai_topic_study_plan.py` (3; the first fails without the fix).
Limit: free-text answers with such a topic are still the placeholder, and aliases ("RNN") are not accepted as topics.

## Oversized known/studied names refused (2026-10-30)

Gap (reproduced): the HTTP analyze form bounds the upload (100 MB), the saved plan (1 MB) and a question (MAX_QUESTION_CHARS) but not `known` / `studied` names; a 1 MB name was analysed and echoed back in full inside a ~1 MB warning in a 200 response.
Names over 200 characters (no concept comes close) now get a 422 (`stage: input`) before any analysis, without echoing the value. Tests: `test_prereqai_concept_name_length.py` (3: both fields refused, limit-length still accepted).
Limits: the CLI is not bounded (a local user's own shell); the number of entries is bounded only by the framework's multipart field limit (20000 entries gave a 400).

## Unanswerable questions say what can be asked (2026-10-30)

Usability gap (reproduced): `ask ... "Why is the sky blue?"` (or any question the built-in tutor does not match) ended on "A tutoring model has not yet been configured." plus a warning that it is a placeholder, with no hint of what the release can answer, so a learner
could not tell a wrong question from a missing feature. The warning (CLI and `POST /question`) now ends with the questions that do work: `What is <concept>?`, `What should I study first?`, `How long will it take?`, `Am I ready?`, `Quiz me`.
The answer text itself is unchanged (older tests pin it); answerable questions get no hint. Tests: `test_prereqai_placeholder_guidance.py` (2, run through the real CLI and API). Not verified: the wording with real users.

## Detector term-overlap checks cached (2026-10-30)

Bottleneck (profiled, `cProfile` over 5 analyses of the sample paper): `RuleBasedConceptDetector.detect` was ~90% of an analysis (0.44 of 0.49 s), and most of it was independent of the paper: the "does this term contain that term" checks ran
`re.search(re.escape(...))` for every pair of concepts x aliases on every call, a cost that grows with the registry (44 concepts now). The pure pair check is now cached (`_word_in`) and `_aliases` is cached per (frozen) concept.
Measured on a 19-concept text, mean of 30 `detect` calls: 20.5 ms before, 5.6 ms after, with identical detected concepts and counts (compared before/after, and pinned in `test_prereqai_detector_term_cache.py`, 2 tests). Timing is not asserted in tests (flaky); one machine, one run each.
Not changed: the per-term scans of the paper text itself (already guarded by a substring check).

## README HTTP API table matches the endpoints (2026-10-30)

Mismatch (checked against the running app): the README's HTTP API table said `analyze` takes only `paper` and answers 422 for "no `paper` field", but the endpoint also takes `source`, `known`, `studied` and `resume` and refuses neither/both of `paper`/`source`, an invalid `source`, an oversized name and a non-plan `resume` with 422;
it said a question `topic` must be one of the paper's concepts (study-plan concepts are accepted since the topic entry above); and it said sessions always end with the server process (not so with `PREREQAI_SESSION_DIR`). Error envelopes were checked on 13 failure cases and all carry `status`, `stage`, `detail`, `hint`, `warnings` as documented, so no code change.
Test: `test_prereqai_http_contract_table.py` (3, exercising each documented claim through the app). Limit: only this table was checked, not every sentence of the README.

## First run from another directory (2026-10-30)

Clean-environment check first: in a fresh venv, `pip install -r requirements.txt` then the README quickstart (CLI analysis, `uvicorn` + `/health` + the curl analysis of the sample paper) all worked (Python 3.13; exit 0). The obstacle found: running the quickstart from any directory other than the
repository root fails with Python's bare `No module named 'backend'` (reproduced from `/tmp`), and the README only said "from the repository root". The README now says what the error looks like and the two working alternatives (`PYTHONPATH=/path/to/PreReqAI`, `uvicorn --app-dir`).
Test: `test_prereqai_run_from_another_directory.py` (2: the PYTHONPATH route runs from a temp directory; without it the documented error appears). The CLI route is covered by the test; the `--app-dir` form was run by hand from `/tmp` (`/health` answered ok) and is not in the automated test.

## CI checks the runtime-only install (2026-10-30)

Gap: every CI step ran in an environment built from `requirements-dev.txt` (pytest, httpx2 on top of the runtime), so a runtime import of a dev-only package, or of one missing from `requirements.txt`, would pass CI and only fail for a user following the README (`pip install -r requirements.txt`).
Added (1) a CI step that creates a venv, installs only `requirements.txt` and runs the README quickstart, and (2) `test_prereqai_runtime_dependencies.py` (3): importing `backend.cli` and `backend.main` loads only packages that `requirements.txt` (and their dependencies) provide, a sanity test proving the probe flags `pytest`, and a check that the workflow has the step.
Optional SDK imports (Gemini/OpenAI adapters, anyio's sniffio) are hidden in the probe, as they are not runtime requirements. Locally verified: the new tests pass and the quickstart works in a runtime-only venv (also checked in commit 11); the new CI step itself runs only on GitHub and has not been run there.
Limit: the probe covers what the CLI and server import at startup, not lazily imported modules.

## Venue section headings (2026-10-30), and the state of the January blockers

Gap (probed with 40 headings): the section parser missed headings that conference papers use, so the text after them folded into the previous section: `Reference`, `References:` (trailing colon), `Literature Cited`, NeurIPS's `Acknowledgments and Disclosure of Funding`,
`Conclusion and Discussion` / `Discussion and Conclusion`, `Limitations and Future Work`, `Results and Analysis`, `Experiments and Results`, `Broader Impact Statement`, `Appendix A`, `Supplementary Materials`. The costly case is the bibliography: unless a heading ends the previous section the reference
list is read as body text and its paper titles are counted as concepts. All are now headings (an optional trailing colon on any known heading; a bare trailing period is deliberately not accepted, as "Notation." is a sentence). Test: `test_prereqai_venue_section_headings.py`
(a parametrised positive list, sentences that must stay body text, and a three-heading document). Still unrecognised: a named appendix such as `Appendix A: Proofs`, `Summary`, `Motivation`, `Contributions` (too ambiguous to add blind).

Status of the January items, re-checked today: the 44 workspace/projection failures are gone (`pytest backend/tests/test_research_workspace_*.py backend/tests/test_consumer_projection_*.py`: 4112 passed, 0 failed); a real published paper has still not been run (no network here);
the tutor is still the disclosed placeholder (provider decision); Python 3.10 is still not run locally (3.11 and 3.12 interpreters exist here, 3.10 does not; CI runs 3.10).

## Embeddings recognised (2026-10-31)

Gap (from the "still undetected" list above): embeddings, central to language and graph papers, were not detected. Added the Embedding concept (plural handled by the matcher; alias `word2vec`) with a definition and prerequisites (Linear Algebra, Neural Networks). Test: `test_prereqai_embedding_concept.py` (2: detection with prerequisites/definition; look-alike "embedded" and a References title must not match).
Known limit: the bare word "embedding" in a non-ML sense ("embedding a video") would count. Still undetected: regularisation, convolution, autoregressive models, Markov chains, KL divergence, contrastive learning, distillation, mixture of experts.

## Named appendix headings (2026-10-31)

Defect (reproduced): `Appendix A: Proofs`, `Appendix B. Additional Experiments` and `Appendix: Proofs` were not recognised as headings, so an appendix after the bibliography was folded into References. Fix: the section pattern accepts `Appendix`, an optional letter/number, a `:`/`.`/dash separator and a title-cased title (same word rules as numbered headings), so sentences such as "Appendix A: we show ..." or "See Appendix A: Proofs for details." stay body text. Test: `test_prereqai_named_appendix_heading.py` (the section test fails without the fix). Still unrecognised: `Summary`, `Motivation`, `Contributions`, `Appendix A.1 Details`.

## Resume honours a hand-edited "Already known" line (2026-10-31)

Workflow gap (reproduced): the save -> edit -> `--resume` loop broke at the edit step. `Already known: Linear Algebra, Calculus` (commas, as the `--known` flag and README use) was read as ONE concept named "Linear Algebra, Calculus" and ignored, and a lower-case `already known:` line was not read at all, so those concepts silently came back into the plan. `known_from_plan` now splits on `;` or `,` and matches the label case-insensitively; the CLI and HTTP `resume` share it. Test: `test_prereqai_resume_hand_edited_known.py` (3 of 5 cases fail without the fix). Limit: a concept name containing a comma would be split (none exists in the registry).

## One mention counted once when a name contains its own alias (2026-10-31)

Invariant: a single mention is a single occurrence. Evidence (reproduced): the detector subtracted overlaps between a concept's aliases but not between its NAME and an alias, so "Monte Carlo Method" counted 2, "Monte Carlo Methods" 2, "Maximum Likelihood Estimation (MLE)" 3 (should be 2: the name and the abbreviation), "stochastic gradient descent (SGD)" 3 (should be 2). Occurrence counts rank concepts, so the inflated ones were over-weighted. Fix: `mentions()` in `rule_based_concept_detector.py` now includes the concept name in the overlap check. Test: `test_prereqai_overlapping_terms_counted_once.py` (all 5 cases fail without the fix). Limit: overlaps between different concepts were already handled; a concept whose alias equals its name case-insensitively is still counted twice (none in the registry).
