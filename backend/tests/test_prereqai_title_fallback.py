import pymupdf

from backend.cli import main
import json


def _pdf(path, with_title):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 60), "Author Names and Affiliation", fontsize=10)
    page.insert_text((50, 100), "Denoising Diffusion Probabilistic Models", fontsize=20)
    page.insert_text((50, 140), "Abstract. We use diffusion models and attention.", fontsize=10)
    if with_title:
        doc.set_metadata({"title": "Embedded Title"})
    doc.save(path)


def test_a_pdf_without_title_metadata_is_titled_from_its_first_page(tmp_path, capsys):
    path = tmp_path / "paper.pdf"
    _pdf(path, with_title=False)
    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["report"]["paper"]["title"] == "Denoising Diffusion Probabilistic Models"


def test_embedded_title_metadata_still_wins(tmp_path, capsys):
    path = tmp_path / "paper.pdf"
    _pdf(path, with_title=True)
    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["report"]["paper"]["title"] == "Embedded Title"
