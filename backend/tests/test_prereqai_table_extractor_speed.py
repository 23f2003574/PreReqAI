"""The table extractor skips pages that draw no lines or rectangles (pdfplumber's default detection
cannot find a table there, and loading such pages was ~98% of a 40-page analysis: about 6.4s -> 0.1s).
Skipping must never change which tables are found."""
from types import SimpleNamespace

import pymupdf

from backend.parsing.table_extractor import TableExtractor


def _pdf(tmp_path):
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Page one is plain text only.", fontsize=11)
    ruled = document.new_page()
    left, top, width, height = 72, 100, 80, 24
    for row in range(3):
        for column in range(2):
            rect = pymupdf.Rect(left + column * width, top + row * height, left + (column + 1) * width, top + (row + 1) * height)
            ruled.draw_rect(rect)
            ruled.insert_text((rect.x0 + 6, rect.y0 + 16), f"r{row}c{column}", fontsize=10)
    document.new_page().insert_text((72, 72), "Page three is plain text only.", fontsize=11)
    path = tmp_path / "tables.pdf"
    document.save(path)
    return str(path)


def _tables(path):
    return [(t.table_id, t.page_number, t.rows) for t in TableExtractor().extract(path, SimpleNamespace(tables=None)).tables]


def test_skipping_undrawn_pages_finds_exactly_the_same_tables(tmp_path, monkeypatch):
    path = _pdf(tmp_path)
    fast = _tables(path)

    monkeypatch.setattr(TableExtractor, "_pages_with_vector_graphics", staticmethod(lambda _path: None))  # examine every page
    exhaustive = _tables(path)

    assert fast == exhaustive
    assert [(table_id, page) for table_id, page, _ in fast] == [(1, 2)]
    assert fast[0][2] == [["r0c0", "r0c1"], ["r1c0", "r1c1"], ["r2c0", "r2c1"]]


def test_plain_text_pages_are_not_handed_to_pdfplumber(tmp_path, monkeypatch):
    document = pymupdf.open()
    for _ in range(3):
        document.new_page().insert_text((72, 72), "text only", fontsize=11)
    path = tmp_path / "plain.pdf"
    document.save(path)

    import pdfplumber.page

    def _unexpected(self, *args, **kwargs):
        raise AssertionError("extract_tables ran on a page without lines or rectangles")

    monkeypatch.setattr(pdfplumber.page.Page, "extract_tables", _unexpected)
    assert TableExtractor().extract(str(path), SimpleNamespace(tables=None)).tables == []
