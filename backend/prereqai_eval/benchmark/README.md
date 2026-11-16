# Real-paper benchmark

`python -m backend.prereqai_eval --benchmark [--manifest FILE] [--json]` runs reviewed real academic PDFs through the production pipeline
(offline, no LLM) and reports, per paper and in total, concept precision/recall/F1, heading and section-role accuracy, section-specific
occurrence agreement and prerequisite-coverage precision/recall, with every false positive and false negative named. It is reported apart from the
synthetic `--pdf` evaluation and never merged with it.

## Current state (read this first)

**No paper is evaluable yet, so there are no real-paper results.** `manifest.json` lists five well-known papers (title, authors, source link,
venue and year) but each has `license.status: "unverified"`, no PDF and a `pending_review` annotation. The environment this was built in could not
reach arxiv.org, so no licence could be checked and no PDF obtained; nothing was assumed. A paper takes part in the metrics only when **all** hold:
a verified redistribution licence (`spdx` one of the listed licences, with `evidence_url` and `verified_on`), its PDF in `pdfs/` whose sha256 matches
the manifest, and an annotation that a named person approved. Anything else is listed under `excluded` with its reason.

## Adding a paper
1. Check the paper's licence at its source (for arXiv, the licence link on the abstract page); only papers licensed for redistribution may be added.
2. Put the PDF in `pdfs/<id>.pdf`; record `pdf.path`, `pdf.sha256` (`sha256sum`), `retrieved_on`, and `license` `{status: "verified", spdx, evidence_url, verified_on}`.
3. Write `annotations/<id>.json` (format `prereqai-benchmark-annotation`, `schema_version` 1): `sections` `[{title, role: instructional|related|other}]`,
   `concepts` `[{name, occurrences: {section title: count}}]` (registry concept names), `prerequisites` `[{concept, covered}]`, and `review: {status: "pending_review"}`.
   Annotate from the paper by reading it, not from PreReqAI's output; a machine-made draft stays `pending_review`.
4. A person who checked it approves it: `python -m backend.prereqai_eval --approve benchmark/annotations/<id>.json --reviewer "Name"`.

Validation reports every invalid identifier, missing field, duplicate and section reference that is not in `sections`.
