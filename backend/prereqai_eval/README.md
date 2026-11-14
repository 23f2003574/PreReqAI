# PreReqAI detection evaluation (synthetic fixtures, text mode only)

**Read this first.** This harness scores PreReqAI's detectors on six short texts written for this repository. It does **not** read PDFs and it is
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

## What it measures

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
- **No PDF mode.** An evaluation that renders the fixtures as PDFs and runs the whole pipeline (ingestion, section parsing, coverage) is not
  implemented; until it exists, nothing in this directory validates those stages.
