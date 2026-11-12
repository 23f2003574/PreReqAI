# PreReqAI detection evaluation

```bash
python -m backend.prereqai_eval          # per-fixture and micro precision / recall / F1
python -m backend.prereqai_eval --json   # the full report, including missed and spurious items
python -m backend.prereqai_eval --fixtures my-annotations.json
```

Offline and deterministic: it runs the real concept detector, prerequisite rules and coverage analysis on the text in
`fixtures/papers.json` and compares the result with the annotations. Exit code 2 means the annotation file is malformed.

## Fixtures and provenance

Six short texts. Five are **original summaries written for this repository** of well-known public papers (Transformer, LoRA,
RLHF/PPO, graph attention networks, DDPM); the `source` field of each names the paper and its arXiv ID. None copies a paper's
text, so there is no licensing issue. The sixth is an out-of-scope physics text (a negative example).

## Annotations

- `expected_concepts`: registry concepts a reader would say the text discusses (must be registry names, otherwise the file is rejected).
- `expected_prerequisites`: the subjects a learner without background would still have to study.
- `out_of_registry`: real topics in the text that the registry cannot detect; listed for transparency, **not scored**.

## Limitations (read before quoting a number)

- The texts are written around registry vocabulary, so concept precision/recall is **optimistic**: it shows the matcher works on
  such text, not that PreReqAI finds the concepts of arbitrary real papers. Real full-text PDFs (two-column layout, math, references) are not covered.
- One annotator (the author of the fixtures) labelled them and did not use a second reviewer; prerequisite labels are
  judgement calls (for example, whether Probability is needed for a graph-attention paper), so the prerequisite score is indicative only.
- Six fixtures are far too few for statistics. Detection rules are never tuned to these fixtures.
