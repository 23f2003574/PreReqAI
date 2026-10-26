"""PyMuPDF 2.x installs pymupdf-layout and onnxruntime, whose hardware probe writes warnings to stderr on some hosts (GitHub runners) and
broke every CLI test that expects a clean stderr; requirements.txt keeps the 1.x line the product was verified against."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_requirements_cap_pymupdf_below_2():
    line = next(l for l in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines() if l.lower().startswith("pymupdf"))
    assert ",<2" in line.split("#")[0].replace(" ", "")
