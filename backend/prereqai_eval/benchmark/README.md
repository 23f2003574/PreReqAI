# Real-paper benchmark

`python -m backend.prereqai_eval --benchmark [--manifest FILE] [--json]` runs reviewed real academic PDFs through the production pipeline
(offline, no LLM) and reports, per paper and in total, concept precision/recall/F1, heading and section-role accuracy, section-specific
occurrence agreement and prerequisite-coverage precision/recall, with every false positive and false negative named. It is reported apart from the
synthetic `--pdf` evaluation and never merged with it.

## Current state (read this first)

**No paper is scored yet, so there are no real-paper results.** Three papers are in the benchmark with a verified licence and their PDFs: `dpo` (Direct Preference
Optimization, 2305.18290), `mixtral` (Mixtral of Experts, 2401.04088) and `chain-of-thought` (2201.11903), all CC BY 4.0 on their arXiv abstract pages (checked
2026-11-20; `license.verified_by` says who read them). Their annotations are **machine drafts** (`draft_note`): section titles read from the PDFs' headings, roles chosen
by the drafter, and concept counts by literal term matching inside those sections, not by PreReqAI's detector; prerequisite coverage is not annotated (reported as "not
annotated", never scored). They stay `pending_review`, so `--benchmark` excludes them ("annotation pending_review") and reports no metrics. A person must check every
entry against the paper and then run `--approve benchmark/annotations/<id>.json --reviewer "Name"`; only then do the metrics appear. `--status` lists what is still missing.

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
