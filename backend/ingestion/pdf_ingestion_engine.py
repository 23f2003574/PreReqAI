import pymupdf as fitz  # PyMuPDF; "import fitz" prints a deprecation notice to stdout

from dataclasses import dataclass, field

from .document_metadata_extractor import DocumentMetadata
from .text_cleaning import clean_pdf_text, drop_repeated_page_lines  # noqa: F401  (clean_pdf_text is re-exported)

# MuPDF prints its repair diagnostics ("syntax error in array") to stdout, which corrupts `analyze --json` for a damaged PDF. The
# damage is still reported (to the learner, as a warning) through `pdf.is_repaired`, so the raw messages add nothing.
fitz.TOOLS.mupdf_display_errors(False)
fitz.TOOLS.mupdf_display_warnings(False)


@dataclass
class RawPage:
    page_number: int
    text: str
    ocr: bool = False  # the text was recognised from a scanned page image, not read from the PDF's text layer
    ocr_error: str = ""  # a scanned page whose text could not be recognised, and why
    removed_lines: int = 0  # running header, footer and page-number lines taken out of `text` (they repeat on many pages)


@dataclass
class RawDocument:
    source_path: str
    metadata: DocumentMetadata
    pages: list[RawPage] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)


def _three_column_order(lines, width):
    """The (box, text, position) items of a three-column page in reading order, or None when the lines are not three columns.

    A line wider than 60% of the page (title, abstract, figure) separates runs. In each run, narrow lines are grouped by their
    left edge (a gap of more than 5% of the page width starts a column); a run that has exactly three columns of at least two
    lines is read column by column, any other run keeps its original order. None unless some run is three columns, so a one- or
    two-column page is left to `_lines_in_column_order`."""

    items = [(box, text, position) for position, (box, text) in enumerate(lines)]
    runs, current = [], []
    for item in items:
        if item[0][2] - item[0][0] > 0.6 * width:
            runs.extend([current, [item]] if current else [[item]])
            current = []
        else:
            current.append(item)
    if current:
        runs.append(current)
    ordered, found = [], False
    for run in runs:
        columns = []
        for item in sorted(run, key=lambda entry: entry[0][0]):
            if columns and item[0][0] - columns[-1][-1][0][0] <= 0.05 * width:
                columns[-1].append(item)
            else:
                columns.append([item])
        if len(columns) == 3 and all(len(column) >= 2 for column in columns):
            found = True
            ordered.extend(item for column in columns for item in sorted(column, key=lambda entry: entry[2]))
        else:
            ordered.extend(run)
    return ordered if found else None


def _lines_in_column_order(page):
    """The page's text lines (with their boxes) in reading order, or None when the page needs no reordering.

    Some generators write a two-column page's lines alternately (left line 1, right line 1, left line 2, ...), and the text then
    reads across the gutter, so phrases ("policy" / "gradient"), headings and hyphenated words break. Lines are grouped into runs
    between full-width lines (title, abstract, figures); in a run with at least two lines on each side of the page, the left
    column is read before the right one, each in its original order. A page already written column by column, and any
    one-column page, comes out in the same order, so None is returned and its text is used as extracted."""

    middle, slack = page.rect.width / 2, page.rect.width * 0.02
    lines = [
        (line["bbox"], "".join(span["text"] for span in line["spans"]))
        for block in page.get_text("dict")["blocks"] if block.get("type") == 0
        for line in block["lines"]
    ]
    three = _three_column_order(lines, page.rect.width)
    if three is not None:
        if [item[2] for item in three] == list(range(len(lines))):
            return None
        return "\n".join(item[1] for item in three) + "\n"
    ordered, run = [], {"left": [], "right": []}

    def flush():
        ordered.extend(run["left"] + run["right"] if min(len(run["left"]), len(run["right"])) >= 2
                       else sorted(run["left"] + run["right"], key=lambda item: item[2]))
        run["left"], run["right"] = [], []

    for position, (box, text) in enumerate(lines):
        if box[2] <= middle + slack:
            run["left"].append((box, text, position))
        elif box[0] >= middle - slack:
            run["right"].append((box, text, position))
        else:
            flush()
            ordered.append((box, text, position))
    flush()

    if [item[2] for item in ordered] == list(range(len(lines))):
        return None

    return "\n".join(item[1] for item in ordered) + "\n"


def _page_text(page) -> str:

    return _lines_in_column_order(page) or page.get_text("text")


MIN_TEXT_CHARS = 25  # fewer letters and digits than this on a page is "no usable text layer"
MIN_IMAGE_COVER = 0.25  # a scan is a page image covering a good part of the page, not a small logo


def needs_ocr(page, text) -> bool:
    """A page with almost no extractable text whose images cover a meaningful part of it (a scan). A blank page, or a page of
    text with a figure, is not: ordinary text PDFs are never sent to OCR."""
    if sum(char.isalnum() for char in text) >= MIN_TEXT_CHARS:
        return False
    area = page.rect.width * page.rect.height
    if area <= 0:
        return False
    covered = sum(max(0.0, (box[2] - box[0]) * (box[3] - box[1])) for box in (info["bbox"] for info in page.get_image_info()))
    return covered / area >= MIN_IMAGE_COVER


def default_ocr(page) -> str:
    """Recognise a page's text with PyMuPDF's OCR, which needs a system Tesseract (and its language data). Raises RuntimeError
    with the reason when OCR cannot run, so the caller can report it instead of returning an empty page."""
    try:
        if not fitz.get_tessdata():
            raise RuntimeError("Tesseract language data was not found")
        textpage = page.get_textpage_ocr(language="eng", dpi=300, full=True)
        return page.get_text("text", textpage=textpage)
    except RuntimeError:
        raise
    except Exception as error:  # PyMuPDF raises various types when Tesseract is missing or fails
        raise RuntimeError(f"{type(error).__name__}: {error}") from error


def read_page(page, page_number, ocr) -> RawPage:
    """One page in the ingestion format: its text layer when it has one, else (for a scan) OCR output. Never raises for OCR: a
    scan that could not be recognised keeps empty text and says why in `ocr_error`."""
    text = clean_pdf_text(_page_text(page))
    if not needs_ocr(page, text):
        return RawPage(page_number=page_number, text=text)
    try:
        recognised = clean_pdf_text(ocr(page)).strip()
    except Exception as error:
        return RawPage(page_number=page_number, text=text, ocr_error=f"OCR could not run: {error}")
    if not recognised:
        return RawPage(page_number=page_number, text=text, ocr_error="OCR found no text on this scanned page")
    return RawPage(page_number=page_number, text=recognised, ocr=True)


class PDFIngestionEngine:
    """
    Reads a research paper PDF and converts it into
    PreReqAI's raw internal document representation.
    """

    def __init__(self, ocr=None):
        self.ocr = ocr or default_ocr  # callable(page) -> text; replaceable so scanned-page handling is testable without Tesseract

    def ingest(self, file_path: str) -> RawDocument:
        from .document_metadata_extractor import DocumentMetadataExtractor

        # One open of the file serves both the metadata and the page text.
        with fitz.open(file_path) as pdf:

            metadata = DocumentMetadataExtractor().extract_from(pdf)

            pages = [read_page(page, page_number, self.ocr) for page_number, page in enumerate(pdf, start=1)]

        cleaned, removed = drop_repeated_page_lines([page.text for page in pages])  # before any concept is counted
        for page, text, count in zip(pages, cleaned, removed):
            page.text, page.removed_lines = text, count

        return RawDocument(
            source_path=file_path,
            metadata=metadata,
            pages=pages,
        )
