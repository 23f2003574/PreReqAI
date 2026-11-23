# PreReqAI detection evaluation (synthetic fixtures: text mode and PDF mode)

**Read this first.** This harness scores PreReqAI's detectors on six short texts written for this repository. In its default text mode it does **not** read PDFs, and it is
**not** evidence about how PreReqAI behaves on real academic papers. No real published paper has been evaluated or validated yet.

## How to run it

From the repository root, with `pip install -r requirements.txt` done:

```bash
python -m backend.prereqai_eval          # per-fixture and micro precision / recall / F1 (about a second, offline, deterministic)
python -m backend.prereqai_eval --json   # the full report, including the missed and spurious items
python -m backend.prereqai_eval --fixtures my-annotations.json   # your own annotations, same format as fixtures/papers.json
```

Exit code 2 means the annotation file is malformed (the message names the fixture and field). The harness is tested by
`backend/tests/test_prereqai_eval_harness.py` and `test_prereqai_domain_evaluation.py`.

## PDF mode (`--pdf`)

```bash
python -m backend.prereqai_eval --pdf          # readable report; add --json for the full report (needs PyMuPDF, offline, deterministic)
```

Three PDFs are generated with PyMuPDF from `pdf_fixtures.py` (numbered headings, unnumbered headings, and a two-column page with Roman-numbered
headings; each has a running header and page numbers on 3+ pages) and run through the real `ResearchPaperPipeline`: PDF ingestion (header and
footer removal, column order), section parsing, concept and prerequisite detection and section-aware coverage. Annotations say which headings
and roles a reader sees, which registry concepts the text discusses, and which prerequisite subjects it *teaches* in a Background or Method-like
section. The report gives per fixture and in total: heading detection, section-role accuracy, concept precision/recall, coverage
precision/recall, and how many fixtures the pipeline analysed. Annotations were written from the texts' design, never adjusted to a run.

**These PDFs are synthetic, written for this repository. A score on them is not validation on real published papers**, which has still not been done.
On 2026-11-16 the run exposes two real findings (kept visible, not annotated away): `4 Experiments on CIFAR-10` was not recognised as a heading (fixed on 2026-11-23: a title word may now carry digits, as in CIFAR-10 or GPT-4), so
its text was filed under Method and Probability was reported covered; and "Graph Neural Network" counts as Neural Networks subject mentions.

## What it measures (text mode)

For each fixture it builds one paper whose paragraphs all carry the section title `Body`, runs the real `RuleBasedConceptDetector`,
`PrerequisiteDetector` and `MissingPrerequisiteAnalyzer` on that text, and compares the result with the annotations:

- **concepts**: the registry concepts the detector finds against `expected_concepts`;
- **prerequisites**: the subjects still reported as needed (missing and not satisfied) against `expected_prerequisites`.

Output of the command on 2026-11-14 (60-concept registry, 12 prerequisite subjects; re-run it to reproduce):

```
MICRO        concepts      P=1.00 R=1.00 F1=1.00 (tp=39 fp=0 fn=0)
MICRO        prerequisites P=0.75 R=1.00 F1=0.86 (tp=21 fp=7 fn=0)
```

The concept score is perfect because the texts were written around registry vocabulary (below). The prerequisite precision is below 1 because every
paragraph sits in one section named `Body`, which the coverage policy treats as a section that can mention a subject but never "cover" it
(`section_role` in `missing_prerequisite_analyzer.py`; only instructional sections such as Method or Background can). Subjects the fixture
papers themselves discuss therefore still show as needed (the `spurious` items in the output). So the prerequisite numbers do not exercise
section-aware coverage, and they say nothing about it.

## Fixtures and provenance

Six short texts. Five are **original summaries written for this repository** of well-known public papers (Transformer, LoRA, RLHF/PPO, graph
attention networks, DDPM); the `source` field of each names the paper and its arXiv ID. None copies a paper's text, so there is no licensing issue.
The sixth is an out-of-scope physics text (a negative example). The fixtures were written before the classical machine learning concepts were
added to the registry and contain none of them.

## Annotations

- `expected_concepts`: registry concepts a reader would say the text discusses (must be registry names, otherwise the file is rejected).
- `expected_prerequisites`: the subjects a learner without background would still have to study.
- `out_of_registry`: real topics in the text that the registry cannot detect; listed for transparency, **not scored**.

## What is not evaluated (unverified)

None of these stages is measured here, and none has been checked against a real paper: PDF text extraction and column order, header, footer and
page-number removal, ligature and dash cleaning, OCR of scanned pages (the code exists; a real Tesseract run has never been verified), title and
author extraction, section parsing (including headings outside the fixed list), bibliography detection, section-aware coverage on real section
structure, difficulty and study-time estimates, the schedule, the tutor and the quiz. The unit tests of those stages use generated PDFs and
hand-made inputs, which show the logic works as designed, not that it works on published papers. A real-paper check exists as a manual workflow
(`.github/workflows/real-paper-live.yml`, one arXiv paper, loose assertions) and has never been run.

## Limitations (read before quoting a number)

- **Synthetic and optimistic.** The texts use registry vocabulary, so concept precision and recall show that the matcher works on such text, not
  that PreReqAI finds the concepts of arbitrary papers. Concepts outside the registry are not detected at all.
- **One annotator.** The author of the fixtures labelled them, with no second reviewer; the prerequisite labels are judgement calls (for example,
  whether Probability is needed for a graph-attention paper), so the prerequisite score is indicative only.
- **Six fixtures** are far too few for statistics. Detection rules are never tuned to these fixtures.
- **PDF mode is synthetic.** `--pdf` exercises ingestion, section parsing and coverage on three generated PDFs only; no published paper is used.

## Performance (`--performance`)

`python -m backend.prereqai_eval --performance [--pages 120] [--json]` runs a generated academic PDF of at least 100 pages through the real pipeline and prints
the seconds of each stage, the peak Python memory (tracemalloc) and the process's peak resident size, for a cold run and for the same file again (served by the
analysis cache, `backend/analysis_cache.py`). Timings depend on the machine, so tests never assert them; compare runs on one machine.

Measured on the development container (120 pages, 115 KB, one run each, cold, in a fresh process; the numbers move by roughly 0.2 s between runs):

| | before | after |
|---|---|---|
| total | 5.03 s | 3.15-3.35 s |
| concept_detector | 1.50 s | 0.66 s |
| ingestion | 1.21 s | 0.86-0.93 s |
| missing_prerequisite_analyzer | 0.72 s | 0.14 s |
| report_generator | 0.70 s | 0.85 s (now also builds the evidence passages) |
| peak Python memory | 17.5 MiB | 17.3 MiB |
| the same file again | n/a | 0.03 s (cache hit; the pipeline is not rerun) |

The profile (cProfile, cumulative) showed three demonstrated hotspots and only these were changed: the one-off `_shadowing_terms` table built 76,000 regular
expressions for the 116-concept registry (a plain substring test now rejects almost every pair first); `section_mentions` re-ran the detector for every section
twice (the second ask for the same paper now reuses the first answer, keyed by a hash of the paragraphs); and ingestion extracted every page's lines and fonts
twice (once now). Nothing else was tuned. Results are unchanged: the `--pdf` evaluation and the whole test suite give the same answers.


## Held-out invariants (`--heldout`, part of `--gate`)
`heldout/manifest.json` holds three CC BY 4.0 papers the rules were not tuned on (GQA 2305.13245, Mistral 7B 2310.06825, Constitutional AI 2212.08073) with their arXiv source, licence evidence and the SHA-256 of each PDF. They carry no annotations, so nothing here is a score: the gate checks invariants a correct extraction always satisfies and prints exactly what is wrong when one fails: references were extracted (at least 10 entries), no two headings are identical, no heading is shorter than 3 characters, every detected concept is named somewhere outside the bibliography, and every evidence quotation is an exact quotation of the page it cites. It is offline and deterministic. The licences were read from the arXiv abstract pages by an AI assistant, which the manifest and the gate output say; a human should confirm them. A PDF whose SHA-256 changed, a licence not recorded as verified, or a missing file stops the gate with that reason.

## Mathematical subtopics (`--gate`, group `math_subtopics`)

`math_eval.py` scores the rules of `backend/parsing/math_subtopics.py` on `fixtures/math_equations.json`: 34 equations in the style of a PDF text layer with the subtopics a reader needs for each.
**Provenance: written by the AI assistant that built the evaluation, expected subtopics decided by it, not extracted from a real PDF, not reviewed by a human** (`status: ai_written_unreviewed`).
The rules were tightened against this set (the first run scored precision 0.949 and recall 0.918 with 3 false positives and 5 false negatives; they now score 1.0 and 1.0), so the numbers are
optimistic by construction: they are a regression guard, not a measure of real papers. Real-paper equations are **not annotated**: doing it honestly needs the PDF text extraction of the real
papers run and read by a person, because what a rule can see (flattened fractions, lost subscripts, glyph names) is decided there; this was not possible where the evaluation was written (no PyMuPDF).

## Retrieval on real papers (`--gate`, group `retrieval_real`)

`retrieval_real.py` runs 36 questions with gold phrases (`fixtures/retrieval_questions.json`) over the six licensed PDFs and reports recall@5 and MRR for the lexical and the hybrid search, per
paper. **The questions are AI-written and not reviewed by a human**; gold phrases were checked to occur in the papers, but some are generic words, so a hit shows the right region was found. The gate
requires the hybrid search to do at least as well as the lexical one on every paper, every quotation to be exact and the set not to shrink, and holds absolute floors for the hybrid search in
`thresholds.json` (`retrieval_real`): overall recall@5 0.72 and MRR 0.52, and recall@5 per paper. They sit one question below the numbers measured when they were set (hybrid recall@5 0.639, MRR 0.493 at first; 0.750 and 0.559 after the token, rare-term and neighbour-context changes
over 36 questions; per paper chain-of-thought 0.33, constitutional-ai 0.83, dpo 0.50, gqa 0.83, mistral-7b 0.33, mixtral 1.00), so a loss of two questions fails the gate and one does not. They are a
regression guard on AI-written, unreviewed questions: they are not evidence that retrieval is good, and raising them needs a human-reviewed question set. Reproduce with `python -m backend.prereqai_eval --gate`.
