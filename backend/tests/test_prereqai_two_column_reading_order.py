"""Two-column pages whose generator wrote the lines alternately (left 1, right 1, left 2, ...) are read column by column, so
concepts that wrap across lines, section headings and hyphenated words survive; one-column and column-by-column pages are
read exactly as before."""
import pymupdf as fitz
import pytest

from backend.ingestion.pdf_ingestion_engine import PDFIngestionEngine
from backend.platform import PreReqAIPlatform

pytestmark = pytest.mark.prereqai

LEFT = ["Abstract", "We study training with policy", "gradient methods and softmax", "policies for sequence models.", "",
        "1 Introduction", "Gradient descent and back-", "propagation train the network.", "Attention layers help."]
RIGHT = ["2 Method", "We apply a variational auto-", "encoder with KL divergence.", "The graph neural network",
         "passes messages.", "", "References", "[1] Diffusion models."]
EXPECTED = {"Attention", "Backpropagation", "Gradient Descent", "Graph Neural Network", "Policy Gradient", "Softmax",
            "Variational Autoencoder"}


def _pdf(tmp_path, interleaved, name="paper.pdf"):
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((50, 60), "A Two Column Paper", fontsize=14)
    if interleaved:
        for index in range(max(len(LEFT), len(RIGHT))):
            for column, x in ((LEFT, 50), (RIGHT, 320)):
                if index < len(column):
                    page.insert_text((x, 100 + index * 14), column[index], fontsize=10)
    else:
        for column, x in ((LEFT, 50), (RIGHT, 320)):
            for index, line in enumerate(column):
                page.insert_text((x, 100 + index * 14), line, fontsize=10)
    path = tmp_path / name
    path.write_bytes(document.tobytes())
    return str(path)


def _concepts(path):
    outcome = PreReqAIPlatform().analyze(path)
    assert outcome["status"] == "success", outcome
    return {c["name"] if isinstance(c, dict) else c for c in outcome["report"]["concepts"]}


def test_interleaved_columns_give_the_same_concepts_as_column_by_column(tmp_path):
    assert _concepts(_pdf(tmp_path, interleaved=False, name="a.pdf")) == EXPECTED
    assert _concepts(_pdf(tmp_path, interleaved=True, name="b.pdf")) == EXPECTED


def test_interleaved_page_text_reads_left_column_then_right(tmp_path):
    text = PDFIngestionEngine().ingest(_pdf(tmp_path, interleaved=True)).pages[0].text

    assert text.index("We study training with policy") < text.index("2 Method")
    assert "policy gradient methods" in " ".join(text.split())
    assert text.index("2 Method") < text.index("References")  # the right column keeps its own order


def test_a_one_column_page_is_read_exactly_as_extracted(tmp_path):
    document = fitz.open()
    page = document.new_page()
    for index, line in enumerate(["Abstract", "We use softmax and attention.", "1 Introduction", "Short.", "Right aligned"]):
        page.insert_text((72 if line != "Right aligned" else 400, 72 + index * 14), line, fontsize=11)
    path = tmp_path / "one.pdf"
    path.write_bytes(document.tobytes())

    with fitz.open(path) as pdf:
        extracted = pdf[0].get_text("text")
    ingested = PDFIngestionEngine().ingest(str(path)).pages[0].text

    assert ingested.split() == extracted.split()
