from time import perf_counter

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
    ocr_stopped: bool = False  # a scanned page left unread because the OCR time or page budget ran out (ocr_error says which)
    layout: list = field(default_factory=list)  # one dict per text line (text, size, bold, mixed, block_lines, bbox) for heading detection; emptied once sections are parsed
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
    def ocr_complete(self) -> bool:
        """False when scanned pages were left unread because the OCR budget ran out: the document is a partial result."""
        return not any(page.ocr_stopped for page in self.pages)

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


MIN_USABLE_CHARS = 200  # this much text is a real text layer whatever the page also holds (a scan with hidden text, a page with figures)
SCAN_IMAGE_COVER = 0.85  # an image this large is the page itself, not a figure on it
STAMP_MAX_HEIGHT = 0.15  # a stamp, watermark or running header fills a band of the page; text over a larger share is page text


def _text_height_share(page):
    """The share of the page height spanned by its text blocks, or None when the page offers no block geometry."""
    try:
        blocks = page.get_text("blocks")
        spans = [(block[1], block[3]) for block in blocks if len(block) > 4 and str(block[4]).strip()]
    except Exception:
        return None
    if not isinstance(blocks, list) or not spans or page.rect.height <= 0:
        return None
    return (max(end for _, end in spans) - min(start for start, _ in spans)) / page.rect.height


def needs_ocr(page, text) -> bool:
    """Whether a page is a scan whose text must be recognised. A blank page, a page of text with a figure and a page with a real text
    layer (MIN_USABLE_CHARS or more) are not, so ordinary text PDFs are never sent to OCR. A page with almost no text whose images cover
    a meaningful part of it is. A page-sized image (SCAN_IMAGE_COVER) with a short text layer confined to a narrow band (a stamp, watermark,
    page number or running header, STAMP_MAX_HEIGHT) is a scan too; without block geometry a short text layer counts as usable text."""
    letters = sum(char.isalnum() for char in text)
    if letters >= MIN_USABLE_CHARS:
        return False
    area = page.rect.width * page.rect.height
    if area <= 0:
        return False
    covered = sum(max(0.0, (box[2] - box[0]) * (box[3] - box[1])) for box in (info["bbox"] for info in page.get_image_info()))
    share = covered / area
    if letters < MIN_TEXT_CHARS:
        return share >= MIN_IMAGE_COVER
    height = _text_height_share(page)
    return share >= SCAN_IMAGE_COVER and height is not None and height <= STAMP_MAX_HEIGHT


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


def _layout_lines(page):
    """The typography of the page's text lines: text, font size (of the longest span), bold (every span bold), mixed (bold and regular
    spans in one line, e.g. a bold lead-in of a paragraph), the number of lines in its block and its box. [] when unavailable."""
    try:
        blocks = page.get_text("dict")["blocks"]
    except Exception:
        return []
    found = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            spans = [span for span in line["spans"] if span["text"].strip()]
            if not spans:
                continue
            weights = [bool(span["flags"] & 16) or "bold" in span["font"].lower() for span in spans]
            main = max(spans, key=lambda span: len(span["text"]))
            found.append({"text": "".join(span["text"] for span in line["spans"]).strip(), "size": round(main["size"], 1),
                          "chars": sum(len(span["text"].strip()) for span in spans), "bold": all(weights),
                          "mixed": any(weights) and not all(weights), "block_lines": len(block["lines"]),
                          "bbox": [round(v, 1) for v in line["bbox"]]})
    return found


def read_page(page, page_number, ocr, stop=None) -> RawPage:
    """One page in the ingestion format: its text layer when it has one, else (for a scan) OCR output. Never raises for OCR: a
    scan that could not be recognised keeps empty text and says why in `ocr_error`. `stop` (optional) is asked before a scan is
    recognised and returns why OCR must stop ("" to go on); the page then keeps its text layer, is marked `ocr_stopped` and is not recognised."""
    text = clean_pdf_text(_page_text(page))
    if not needs_ocr(page, text):
        return RawPage(page_number=page_number, text=text, layout=_layout_lines(page))
    reason = stop() if stop is not None else ""
    if reason:
        return RawPage(page_number=page_number, text=text, ocr_error=reason, ocr_stopped=True)
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

    def __init__(self, ocr=None, max_ocr_seconds=None, max_ocr_pages=None, clock=perf_counter):
        self.ocr = ocr or default_ocr  # callable(page) -> text; replaceable so scanned-page handling is testable without Tesseract
        # The OCR budget of one ingestion: seconds from its start and pages recognised. Checked before every scan, never inside a
        # recognition, so a document stops at a page boundary and keeps everything read so far. None means no limit.
        self.max_ocr_seconds, self.max_ocr_pages, self.clock = max_ocr_seconds, max_ocr_pages, clock

    def ingest(self, file_path: str) -> RawDocument:
        from .document_metadata_extractor import DocumentMetadataExtractor

        # One open of the file serves both the metadata and the page text.
        with fitz.open(file_path) as pdf:

            metadata = DocumentMetadataExtractor().extract_from(pdf)

            started, recognised = self.clock(), [0]

            def stop():
                if self.max_ocr_pages is not None and recognised[0] >= self.max_ocr_pages:
                    return f"the OCR limit of {self.max_ocr_pages} pages was reached"
                if self.max_ocr_seconds is not None and self.clock() - started >= self.max_ocr_seconds:
                    return f"the OCR time limit of {self.max_ocr_seconds:g} seconds was reached"
                return ""

            def counted(page):
                recognised[0] += 1
                return self.ocr(page)

            pages = [read_page(page, page_number, counted, stop) for page_number, page in enumerate(pdf, start=1)]

        cleaned, removed = drop_repeated_page_lines([page.text for page in pages])  # before any concept is counted
        for page, text, count in zip(pages, cleaned, removed):
            page.text, page.removed_lines = text, count

        return RawDocument(
            source_path=file_path,
            metadata=metadata,
            pages=pages,
        )
