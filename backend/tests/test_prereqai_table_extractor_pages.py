from types import SimpleNamespace

import pymupdf

from backend.parsing.table_extractor import TableExtractor


def _pdf(path, ruled_page=None, pages=3):
    document = pymupdf.open()
    for number in range(1, pages + 1):
        page = document.new_page()
        page.insert_text((50, 40), f"page {number}")
        if number == ruled_page:
            for i in range(3):  # a 2x2 ruled grid
                page.draw_line((50, 100 + i * 30), (250, 100 + i * 30))
                page.draw_line((50 + i * 100, 100), (50 + i * 100, 160))
            for row, y in enumerate((120, 150)):
                for col, x in enumerate((60, 160)):
                    page.insert_text((x, y), f"r{row}c{col}")
    document.save(str(path))
    return str(path)


def _tables(path):
    return TableExtractor().extract(path, SimpleNamespace(tables=[])).tables


def test_table_on_a_later_page_keeps_its_real_page_number(tmp_path):
    tables = _tables(_pdf(tmp_path / "t.pdf", ruled_page=2))
    assert [(t.table_id, t.page_number) for t in tables] == [(1, 2)]
    assert tables[0].rows == [["r0c0", "r0c1"], ["r1c0", "r1c1"]]


def test_document_with_no_drawings_has_no_tables_without_opening_pdfplumber(tmp_path, monkeypatch):
    path = _pdf(tmp_path / "plain.pdf")
    monkeypatch.setattr("backend.parsing.table_extractor.pdfplumber.open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("opened")))
    assert _tables(path) == []
