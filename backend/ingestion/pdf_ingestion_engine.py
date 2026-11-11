import pymupdf as fitz  # PyMuPDF; "import fitz" prints a deprecation notice to stdout

from dataclasses import dataclass, field

from .document_metadata_extractor import DocumentMetadata
from .text_cleaning import clean_pdf_text  # noqa: F401  (re-exported)

# MuPDF prints its repair diagnostics ("syntax error in array") to stdout, which corrupts `analyze --json` for a damaged PDF. The
# damage is still reported (to the learner, as a warning) through `pdf.is_repaired`, so the raw messages add nothing.
fitz.TOOLS.mupdf_display_errors(False)
fitz.TOOLS.mupdf_display_warnings(False)


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
