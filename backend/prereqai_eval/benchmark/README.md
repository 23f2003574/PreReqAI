# Real-paper benchmark

`python -m backend.prereqai_eval --benchmark [--manifest FILE] [--json]` runs reviewed real academic PDFs through the production pipeline
(offline, no LLM) and reports, per paper and in total, concept precision/recall/F1, heading and section-role accuracy, section-specific
occurrence agreement and prerequisite-coverage precision/recall, with every false positive and false negative named. It is reported apart from the
synthetic `--pdf` evaluation and never merged with it.

## Current state (read this first)

**Three real papers are scored**, all CC BY 4.0 on their arXiv abstract pages (checked 2026-11-20; `license.verified_by` says who read them): `dpo` (Direct Preference
Optimization, 2305.18290), `mixtral` (Mixtral of Experts, 2401.04088) and `chain-of-thought` (2201.11903). Their annotations were drafted by a machine and reviewed and approved
by the AI assistant on the repository owner's instruction (`review.reviewer`, `review_note`): **not by a human reader**, so a person should re-check them before the numbers are
quoted. Prerequisite coverage is not annotated, so it is reported as "not annotated" and never scored.

Results (`python -m backend.prereqai_eval --benchmark`): headings P=0.85 R=0.95 F1=0.90 (tp=41 fp=7 fn=2; 0.44 before numbered headings were read as one line and
name lists were rejected), concepts P=1.00 R=1.00 F1=1.00 (tp=34 fp=0 fn=0; P was 0.92 before the CNN/DailyMail, everyday-"attention" and finetune fixes). The annotations list the numbered sections only (`heading_scope: top-level`), so numbered sub-sections
("5.2 ...") are not counted as false positives. What the errors show:
* headings: generic one-word lines ("Model", "Dataset", "Results") in tables are still read as headings in some papers, and Mixtral's "5 Routing analysis" is missed;
* concepts: recall is 1.00; the false positives are the "CNN" of CNN/DailyMail, an everyday "attention" in a prompt and a "Fine-Tuning" in the CoT paper that was not traced.
Occurrence counts per section mostly disagree because the headings are missed: the counts then land in the wrong section.

The five papers listed first (Attention Is All You Need, LoRA, DDPM, Adam, Batch Normalization) are under arXiv's non-exclusive distribution licence, which does not allow
redistributing their PDFs, so they cannot be added unless their authors' licence says otherwise; their manifest entries say so.

A paper takes part in the metrics only when **all** hold: a verified redistribution licence (`spdx` one of the listed licences, with `evidence_url` and `verified_on`), its PDF in
`pdfs/` whose sha256 matches the manifest, and an annotation that a named person approved. Anything else is listed under `excluded` with its reason.

## Adding a paper
1. Check the paper's licence at its source (for arXiv, the licence link on the abstract page); only papers licensed for redistribution may be added.
2. Put the PDF in `pdfs/<id>.pdf`; record `pdf.path`, `pdf.sha256` (`sha256sum`), `retrieved_on`, and `license` `{status: "verified", spdx, evidence_url, verified_on}`.
3. Write `annotations/<id>.json` (format `prereqai-benchmark-annotation`, `schema_version` 1): `sections` `[{title, role: instructional|related|other}]`,
   `concepts` `[{name, occurrences: {section title: count}}]` (registry concept names), `prerequisites` `[{concept, covered}]`, and `review: {status: "pending_review"}`.
   Annotate from the paper by reading it, not from PreReqAI's output; a machine-made draft stays `pending_review`.
4. A person who checked it approves it: `python -m backend.prereqai_eval --approve benchmark/annotations/<id>.json --reviewer "Name"`.

Validation reports every invalid identifier, missing field, duplicate and section reference that is not in `sections`.

## Adding a paper with the tools (`--register`, `--status`)
`python -m backend.prereqai_eval --status` lists, for every paper, everything still missing before it can be scored (licence, PDF, hash, annotation content, review).

After you have read the licence on the paper's source page, a PDF you may redistribute is added with:

```bash
python -m backend.prereqai_eval --register paper.pdf --id my-paper --licence CC-BY-4.0 \
  --licence-evidence https://example.org/where-the-licence-is-stated --licence-checked-by "Your Name" \
  --title "..." --author "A. Writer" --source-url https://... --venue "..." --year 2024
```

It copies the PDF to `pdfs/my-paper.pdf`, records its SHA-256 and the licence (on the word of the person named: nothing is checked online), and creates a `pending_review`
annotation if none exists (an existing one is never replaced). For an id already in the manifest (the five listed there) only the PDF and licence are filled in. It never
approves an annotation: annotate from the paper by reading it, then a person runs `--approve`. Nothing is written unless the whole manifest still validates.

## Who approved, and the regression gate

An approved annotation records **who** approved it: `review.reviewer_kind` is `human` or `ai` (`--approve FILE --reviewer "Name" [--reviewer-kind ai]`; the default is human). Only a human's
approval makes a paper's scores human-reviewed; an AI's, or an approval that does not say (older files), makes them **provisional**, and so does a pending annotation never gets scored at all.
`--benchmark` reports `human_reviewed` and `provisional` aggregates apart, with `status` `human_reviewed`, `provisional` or `no_scores`. The three shipped annotations are approved by an AI:
every real-paper number here is provisional until a person re-checks the annotations and approves them (`--reviewer-kind human`).

`python -m backend.prereqai_eval --gate` is the regression gate CI runs: the text fixtures, the generated PDFs (headings, roles, concepts, coverage), the evidence passages on those PDFs (concept coverage,
exact quotations, no chart residue, concept mentioned, page known) and the provisional real-paper floors, each against `thresholds.json`. Exit code 1 and a report naming the failed metric and the
false positives and negatives when a floor is missed. Prerequisite coverage is scored for a paper whose annotation lists `prerequisites` (`[{"concept": ..., "covered": true|false}]`) and reported as
not annotated otherwise. Adding papers: `--register` (above) records the licence evidence, the SHA-256 and the pending annotation; a human annotates and approves it.


## Prerequisite precision and recall on the six real papers
`prerequisite_annotations.json` (one level up) lists, for the three benchmark papers and the three held-out papers, the subjects and concepts a reader needs to follow each one, written by an AI assistant from the paper's content before PreReqAI's
output for it was looked at, and **not reviewed by a person** (provisional). `--gate` scores `paper.prerequisites` against it (`prerequisites_real`): the first measurement was precision 0.436 and recall 0.459 (17 true, 22 false positive, 20 missed
over six papers); the floors (0.40 and 0.42) sit just below it and guard against regression only. The misses are mostly concepts the paper itself uses and the table does not list as prerequisites (Reinforcement Learning, Large Language
Model, Fine-Tuning); the false positives are mostly subject-level (Calculus, Probability, Linear Algebra) that the annotator did not consider necessary for following the paper.
