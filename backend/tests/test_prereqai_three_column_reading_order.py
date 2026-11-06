"""A three-column page whose lines are written alternately (column 1 line 1, column 2 line 1, column 3 line 1, ...) is read column by
column; a page already written column by column and a two-column page are unchanged."""
import pymupdf as fitz
import pytest

from backend.ingestion.pdf_ingestion_engine import _page_text

pytestmark = pytest.mark.prereqai


def _page(columns, rows=4, alternate=True, title=False):
    page = fitz.open().new_page()
    if title:  # written first, so it also comes first in the file's own order
        page.insert_text((72, 60), "A Wide Title Line That Spans The Entire Width Of The Page Here And More", fontsize=10)
    xs = [72, 230, 390] if columns == 3 else [72, 330]
    if alternate:
        for row in range(rows):
            for column, x in enumerate(xs):
                page.insert_text((x, 100 + 14 * row), f"c{column}l{row}", fontsize=10)
    else:
        for column, x in enumerate(xs):
            for row in range(rows):
                page.insert_text((x, 100 + 14 * row), f"c{column}l{row}", fontsize=10)
    return page


def test_alternating_three_columns_are_read_column_by_column():
    assert _page_text(_page(3)).split() == [f"c{c}l{r}" for c in range(3) for r in range(4)]


def test_a_full_width_line_separates_runs():
    words = _page_text(_page(3, title=True)).split()
    assert words[:3] == ["A", "Wide", "Title"] and words[-12:] == [f"c{c}l{r}" for c in range(3) for r in range(4)]


def test_column_by_column_pages_and_two_columns_are_unchanged():
    assert _page_text(_page(3, alternate=False)).split() == [f"c{c}l{r}" for c in range(3) for r in range(4)]
    assert _page_text(_page(2)).split() == [f"c{c}l{r}" for c in range(2) for r in range(4)]
