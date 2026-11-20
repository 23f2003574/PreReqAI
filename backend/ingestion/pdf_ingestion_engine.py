import os
import re
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
    ocr_rotation: int = 0  # degrees (90, 180 or 270) the scan was turned before its text could be read; 0 when it was upright
    ocr_quality: float | None = None  # 0..1 plausibility of the recognised text (see ocr_quality); None when no OCR text was judged
    ocr_warning: str = ""  # something the learner must know about this page's OCR that does not make the page unreadable
    ocr_regions: int = 0  # scanned image regions on a page that also has a text layer, recognised and merged into `text`
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


def _lines_in_column_order(page, blocks=None):
    """The page's text lines (with their boxes) in reading order, or None when the page needs no reordering.

    Some generators write a two-column page's lines alternately (left line 1, right line 1, left line 2, ...), and the text then
    reads across the gutter, so phrases ("policy" / "gradient"), headings and hyphenated words break. Lines are grouped into runs
    between full-width lines (title, abstract, figures); in a run with at least two lines on each side of the page, the left
    column is read before the right one, each in its original order. A page already written column by column, and any
    one-column page, comes out in the same order, so None is returned and its text is used as extracted."""

    middle, slack = page.rect.width / 2, page.rect.width * 0.02
    lines = [
        (line["bbox"], "".join(span["text"] for span in line["spans"]))
        for block in (blocks if blocks is not None else page.get_text("dict")["blocks"]) if block.get("type") == 0
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


def _page_text(page, blocks=None) -> str:

    return _lines_in_column_order(page, blocks) or page.get_text("text")


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


class OcrLanguageError(RuntimeError):
    """The OCR language configured in PREREQAI_OCR_LANGS is malformed or its Tesseract language pack is not installed."""


_LANGUAGE_CODE = re.compile(r"^[a-z]{3}(?:_[a-z]{3,8})?$")


def ocr_languages():
    """The Tesseract language codes from PREREQAI_OCR_LANGS (comma, plus or space separated, e.g. "eng,deu"); ["eng"] when unset or blank.
    OcrLanguageError for a code that is not a Tesseract language code, so a typo is reported and never silently replaced by English."""
    raw = os.environ.get("PREREQAI_OCR_LANGS", "").strip()
    codes = [code for code in re.split(r"[,+\s]+", raw.lower()) if code] or ["eng"]
    for code in codes:
        if not _LANGUAGE_CODE.match(code):
            raise OcrLanguageError(f"{code!r} in PREREQAI_OCR_LANGS is not a Tesseract language code (such as eng or deu)")
    return list(dict.fromkeys(codes))


def ocr_language_argument(tessdata):
    """The `language` argument for Tesseract ("eng+deu"); OcrLanguageError naming every requested language whose pack is not in `tessdata`."""
    codes = ocr_languages()
    missing = [code for code in codes if not os.path.exists(os.path.join(str(tessdata), f"{code}.traineddata"))]
    if missing:
        raise OcrLanguageError(f"the Tesseract language pack{'s' if len(missing) > 1 else ''} for {', '.join(missing)} "
                               "(requested in PREREQAI_OCR_LANGS) is not installed, so the scan was not recognised")
    return "+".join(codes)


QUALITY_MIN = 0.6  # recognised text scoring lower is treated as noise and never reaches concept detection
ROTATIONS = (90, 180, 270)
_TOKEN = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*")


def ocr_quality(text):
    """0..1 plausibility of recognised text: the share of its characters that are letters, digits or ordinary punctuation, and the share
    of its words that look like words (letters and digits, and a vowel in a long lower-case Latin word). Garbage from a rotated or
    degraded scan ("xq7#~ zkvt |||") scores low; prose, and acronyms such as "RNN", score high."""
    chars = [char for char in text if not char.isspace()]
    if not chars:
        return 0.0
    ordinary = sum(char.isalnum() or char in ".,;:()-'\"%/+=?![]" for char in chars) / len(chars)
    tokens = text.split()

    def plausible(token):
        word = token.strip(".,;:()'\"?!%/+=[]")
        if not _TOKEN.fullmatch(word):
            return False
        return not (word.isascii() and word.isalpha() and word.islower() and len(word) >= 4 and not set(word) & set("aeiouy"))

    return round(0.4 * ordinary + 0.6 * sum(plausible(token) for token in tokens) / len(tokens), 3)


def _pixmap_text(pixmap, language):
    with fitz.open("pdf", pixmap.pdfocr_tobytes(language=language)) as recognised:
        return recognised[0].get_text("text")


def default_rotated_ocr(page, box, angle):
    """Recognise a page (box None) or one rectangle of it after turning the image by `angle` degrees; RuntimeError when OCR cannot run."""
    try:
        language = ocr_language_argument(fitz.get_tessdata())
        matrix = fitz.Matrix(300 / 72, 300 / 72).prerotate(angle)
        return _pixmap_text(page.get_pixmap(matrix=matrix, clip=fitz.Rect(*box) if box else page.rect), language)
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(f"{type(error).__name__}: {error}") from error


def default_ocr(page) -> str:
    """Recognise a page's text with PyMuPDF's OCR, which needs a system Tesseract (and its language data). Raises RuntimeError
    with the reason when OCR cannot run, so the caller can report it instead of returning an empty page."""
    try:
        tessdata = fitz.get_tessdata()
        if not tessdata:
            raise RuntimeError("Tesseract language data was not found")
        textpage = page.get_textpage_ocr(language=ocr_language_argument(tessdata), dpi=300, full=True)
        return page.get_text("text", textpage=textpage)
    except RuntimeError:
        raise
    except Exception as error:  # PyMuPDF raises various types when Tesseract is missing or fails
        raise RuntimeError(f"{type(error).__name__}: {error}") from error


def _layout_lines(page, blocks=None):
    """The typography of the page's text lines: text, font size (of the longest span), bold (every span bold), mixed (bold and regular
    spans in one line, e.g. a bold lead-in of a paragraph), the number of lines in its block and its box. [] when unavailable."""
    try:
        blocks = blocks if blocks is not None else page.get_text("dict")["blocks"]
    except Exception:
        return []
    found = []
    for block_id, block in enumerate(blocks):
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
                          "bbox": [round(v, 1) for v in line["bbox"]], "block_id": block_id})
    return _merge_same_row(found)


def _merge_same_row(lines):
    """Lines of one block that sit on the same row (a section number set apart from its title, "4" then "Direct Preference Optimization") become one line, left to right, so a
    numbered heading is one heading line and not two lines of a block."""
    merged, rows = [], {}
    for line in lines:
        key = (line["block_id"], round(line["bbox"][1] / 3))  # the same block and a top edge within about 3 points
        if key in rows:
            row = rows[key]
            pair = sorted((row, line), key=lambda item: item["bbox"][0])
            row.update(text=" ".join(item["text"] for item in pair), chars=row["chars"] + line["chars"], bold=row["bold"] and line["bold"],
                       mixed=row["mixed"] or line["mixed"] or row["bold"] != line["bold"], size=row["size"] if row["chars"] >= line["chars"] else line["size"],
                       bbox=[min(row["bbox"][0], line["bbox"][0]), min(row["bbox"][1], line["bbox"][1]), max(row["bbox"][2], line["bbox"][2]), max(row["bbox"][3], line["bbox"][3])])
            row["block_lines"] -= 1
        else:
            rows[key] = line
            merged.append(line)
    for line in merged:
        line.pop("block_id", None)
    return merged


MIN_REGION_SHARE = 0.08  # an image smaller than this share of the page is a logo or an icon, not a scanned passage
REGION_TEXT_COVER = 0.03  # an image whose area is covered this much by extracted text already has its text (a scan with a hidden text layer)
MIN_REGION_LETTERS = 40  # recognised text with fewer letters than this is not a passage (a figure's axis labels)
MAX_REGIONS_PER_PAGE = 4


def _overlap(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def scanned_regions(page):
    """The boxes (x0, y0, x1, y1) of image regions on a page that has a text layer but holds text that layer lacks: images covering
    at least MIN_REGION_SHARE of the page whose area is not already covered by extracted text. [] when the page has no such image or no
    text-block geometry to tell (then the text layer is trusted, as before), so a text-only PDF never costs an OCR call."""
    try:
        area = page.rect.width * page.rect.height
        blocks = page.get_text("blocks")
        if area <= 0 or not isinstance(blocks, list):
            return []
        boxes = [tuple(block[:4]) for block in blocks if len(block) > 4 and str(block[4]).strip()]
        regions = []
        for info in page.get_image_info():
            box = tuple(info["bbox"])
            size = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
            if size < MIN_REGION_SHARE * area or any(box == region for region in regions):
                continue
            if sum(_overlap(box, text) for text in boxes) >= REGION_TEXT_COVER * size:
                continue
            regions.append(box)
        return sorted(regions, key=lambda box: (box[1], box[0]))[:MAX_REGIONS_PER_PAGE]
    except Exception:
        return []


def default_region_ocr(page, box):
    """Recognise the text of one rectangle of a page (rendered at 300 dpi); RuntimeError with the reason when OCR cannot run."""
    try:
        tessdata = fitz.get_tessdata()
        if not tessdata:
            raise RuntimeError("Tesseract language data was not found")
        return _pixmap_text(page.get_pixmap(clip=fitz.Rect(*box), dpi=300), ocr_language_argument(tessdata))
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(f"{type(error).__name__}: {error}") from error


def _recognise(first, rotated, stop):
    """(text, quality, rotation) of a recognition: `first()` upright, and, when its text is non-trivial but implausible, the scan turned by
    90, 180 and 270 degrees through `rotated(angle)` (each attempt asks `stop` first, so the OCR budget holds); the best of them, the
    first one that is good enough winning at once."""
    text = clean_pdf_text(first()).strip()
    best = (ocr_quality(text), text, 0)
    if rotated is not None and len(text) >= 10 and best[0] < QUALITY_MIN:
        for angle in ROTATIONS:
            if stop is not None and stop():
                break
            turned = clean_pdf_text(rotated(angle)).strip()
            candidate = (ocr_quality(turned), turned, angle)
            if candidate[0] > best[0]:
                best = candidate
            if best[0] >= QUALITY_MIN:
                break
    return best[1], best[0], best[2]


def _words(text):
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def _merge_regions(page, text, recovered):
    """The page text with each recognised region's text placed where the region is: the page's text blocks and the regions, top to
    bottom (left to right at the same height)."""
    items = [(block[1], block[0], block[4].strip()) for block in page.get_text("blocks", sort=True) if len(block) > 4 and str(block[4]).strip()]
    items += [(box[1], box[0], recognised) for box, recognised in recovered]
    merged = "\n".join(clean_pdf_text(part) for _, _, part in sorted(items, key=lambda item: (round(item[0]), item[1])))
    return merged if merged.strip() else text


def _read_regions(page, page_number, text, region_ocr, stop, rotated_ocr=None):
    """A text page whose scanned image regions are recognised and merged into its text (see scanned_regions), or None when it has none. A
    region whose recognised text is mostly already in the page, or is too short to be a passage, adds nothing. An exhausted budget
    leaves the remaining regions unread and marks the page `ocr_stopped`; a recogniser that cannot run keeps the text layer."""
    regions = scanned_regions(page)
    if not regions:
        return None
    recovered, reason, known, warnings, rotation = [], "", _words(text), [], 0
    for box in regions:
        reason = stop() if stop is not None else ""
        if reason:
            break
        try:
            recognised, quality, turned = _recognise(lambda: region_ocr(page, box),
                                                     (lambda angle: rotated_ocr(page, box, angle)) if rotated_ocr else None, stop)
        except OcrLanguageError as error:
            warnings.append(str(error))
            break
        except Exception:
            break  # best effort: the page keeps its text layer, and a paper full of figures is not reported as unreadable because OCR is absent
        if recognised and quality < QUALITY_MIN:
            warnings.append(f"a scanned image region on this page was too noisy to trust (quality {quality:.2f}) and was left out")
            continue
        words = _words(recognised)
        if sum(c.isalpha() for c in recognised) >= MIN_REGION_LETTERS and words and len(words & known) < 0.6 * len(words):
            recovered.append((box, recognised))
            rotation = rotation or turned
            known |= words
    if not (recovered or reason or warnings):
        return None
    merged = _merge_regions(page, text, recovered) if recovered else text
    return RawPage(page_number=page_number, text=merged, ocr=bool(recovered), ocr_regions=len(recovered), ocr_error=reason, ocr_rotation=rotation, ocr_warning="; ".join(dict.fromkeys(warnings)),
                   ocr_stopped=bool(reason), layout=_layout_lines(page))


def read_page(page, page_number, ocr, stop=None, region_ocr=None, rotated_ocr=None) -> RawPage:
    """One page in the ingestion format: its text layer when it has one, else (for a scan) OCR output. Never raises for OCR: a
    scan that could not be recognised keeps empty text and says why in `ocr_error`. `stop` (optional) is asked before a scan is
    recognised and returns why OCR must stop ("" to go on); the page then keeps its text layer, is marked `ocr_stopped` and is not recognised."""
    try:  # one extraction of the page's lines and fonts serves both the reading order and the heading layout
        blocks = page.get_text("dict")["blocks"]
    except Exception:
        blocks = None
    text = clean_pdf_text(_page_text(page, blocks))
    if not needs_ocr(page, text):
        if region_ocr is not None and (mixed := _read_regions(page, page_number, text, region_ocr, stop, rotated_ocr)) is not None:
            return mixed
        return RawPage(page_number=page_number, text=text, layout=_layout_lines(page, blocks))
    reason = stop() if stop is not None else ""
    if reason:
        return RawPage(page_number=page_number, text=text, ocr_error=reason, ocr_stopped=True)
    try:
        recognised, quality, rotation = _recognise(lambda: ocr(page), (lambda angle: rotated_ocr(page, None, angle)) if rotated_ocr else None, stop)
    except Exception as error:
        return RawPage(page_number=page_number, text=text, ocr_error=f"OCR could not run: {error}")
    if not recognised:
        return RawPage(page_number=page_number, text=text, ocr_error="OCR found no text on this scanned page")
    if quality < QUALITY_MIN:  # noise is not content: it is kept out of the text, so no concept is detected from it
        return RawPage(page_number=page_number, text=text, ocr_quality=quality,
                       ocr_error=f"the recognised text was too noisy to trust (quality {quality:.2f}; the scan may be skewed, faint or in another language, see PREREQAI_OCR_LANGS)")
    return RawPage(page_number=page_number, text=recognised, ocr=True, ocr_rotation=rotation, ocr_quality=quality)


class PDFIngestionEngine:
    """
    Reads a research paper PDF and converts it into
    PreReqAI's raw internal document representation.
    """

    def __init__(self, ocr=None, max_ocr_seconds=None, max_ocr_pages=None, clock=perf_counter, region_ocr=None, rotated_ocr=None):
        self.rotated_ocr = rotated_ocr or default_rotated_ocr  # callable(page, box or None, angle) -> text of the image turned by `angle`
        self.region_ocr = region_ocr or default_region_ocr  # callable(page, box) -> text for a scanned region of a page that has a text layer
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

            def counted_region(page, box):
                recognised[0] += 1  # a region counts against the same page budget as a scanned page
                return self.region_ocr(page, box)

            def counted_rotation(page, box, angle):
                recognised[0] += 1  # every extra recognition is OCR work against the same budget
                return self.rotated_ocr(page, box, angle)

            pages = [read_page(page, page_number, counted, stop, counted_region, counted_rotation) for page_number, page in enumerate(pdf, start=1)]

        cleaned, removed = drop_repeated_page_lines([page.text for page in pages])  # before any concept is counted
        for page, text, count in zip(pages, cleaned, removed):
            page.text, page.removed_lines = text, count

        return RawDocument(
            source_path=file_path,
            metadata=metadata,
            pages=pages,
        )
