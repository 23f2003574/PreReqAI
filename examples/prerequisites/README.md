# Prerequisite Explorer example: sample paper

| File | What it is |
| --- | --- |
| `sample-paper.pdf` | A one-page, text-based paper ("Attention Is All You Need", abridged) used by the README quickstart. It analyses offline with no API keys. |
| `make_sample_paper.py` | Rebuilds `sample-paper.pdf` deterministically from the text it contains. |

From the repository root:

```bash
python -m backend.cli prerequisites analyze examples/prerequisites/sample-paper.pdf
python examples/prerequisites/make_sample_paper.py   # rebuild the PDF after editing its text
```

`backend/tests/test_prereqai_quickstart.py` fails if the committed PDF drifts from what
`make_sample_paper.py` builds, or if the quickstart command stops succeeding on it.
