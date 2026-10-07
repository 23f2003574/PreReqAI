"""Rebuilds sample-paper.pdf, the quickstart's input: a one-page, text-based
paper small enough to analyse offline in well under a second. Run from the
repository root:

    python examples/prerequisites/make_sample_paper.py

The output is deterministic for a given PyMuPDF version (fixed metadata, no
timestamps); across versions the bytes may differ but the content does not."""
from pathlib import Path

import pymupdf

TITLE = "Attention Is All You Need"
BODY = """Abstract
We propose the Transformer, a model based on attention. It uses softmax, matrix multiplication and gradient descent.

1 Introduction
Recurrent neural networks and backpropagation are standard for sequence modelling. We use attention and softmax instead.

2 Method
Scaled dot-product attention computes softmax(QK^T / sqrt(d)) V using matrix multiplication.

3 Experiments
We train with gradient descent on a translation task.
"""
OUTPUT = Path(__file__).with_name("sample-paper.pdf")


def build() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 80), TITLE, fontsize=18)
    page.insert_textbox(pymupdf.Rect(72, 110, 540, 770), BODY, fontsize=11)
    document.set_metadata({"title": f"{TITLE} (PreReqAI sample paper)", "creationDate": "", "modDate": "",
                           "producer": "", "creator": ""})
    return document.tobytes(garbage=4, deflate=True, no_new_id=True)


if __name__ == "__main__":
    OUTPUT.write_bytes(build())
    print(f"wrote {OUTPUT}")
