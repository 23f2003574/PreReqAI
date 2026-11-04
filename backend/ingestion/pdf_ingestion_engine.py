import pymupdf as fitz  # PyMuPDF; "import fitz" prints a deprecation notice to stdout

from dataclasses import dataclass, field

from .document_metadata_extractor import DocumentMetadata
from .text_cleaning import clean_pdf_text  # noqa: F401  (re-exported)


@dataclass
class RawPage:
    page_number: int
    text: str


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


class PDFIngestionEngine:
    """
    Reads a research paper PDF and converts it into
    PreReqAI's raw internal document representation.
    """

    def ingest(self, file_path: str) -> RawDocument:
        from .document_metadata_extractor import DocumentMetadataExtractor

        # One open of the file serves both the metadata and the page text.
        with fitz.open(file_path) as pdf:

            metadata = DocumentMetadataExtractor().extract_from(pdf)

            pages = [
                RawPage(
                    page_number=page_number,
                    text=clean_pdf_text(_page_text(page)),
                )
                for page_number, page in enumerate(pdf, start=1)
            ]

        return RawDocument(
            source_path=file_path,
            metadata=metadata,
            pages=pages,
        )
