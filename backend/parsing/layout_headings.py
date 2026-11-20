"""Headings recognised from typography: a short line alone in its block that is set larger than the body text, or bold, and is not a
sentence, caption, author line or title. Used beside the wording rules of the section parser, never instead of them."""
import re
from collections import Counter

_CAPTION = re.compile(r"^(?:fig(?:ure)?|table|algorithm|listing|eq(?:uation)?)\b\.?\s*\d*", re.IGNORECASE)
_PREFIX = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.|[A-Z]\.?)\s+")


def body_size(pages):
    """The font size most characters are set in (the body text), or None without layout."""
    sizes = Counter()
    for page in pages:
        for line in getattr(page, "layout", None) or []:
            sizes[line["size"]] += line["chars"]
    return sizes.most_common(1)[0][0] if sizes else None


def _is_heading(line, body):
    text = line["text"]
    words = text.split()
    if not 1 <= len(words) <= 10 or len(text) > 80 or line["mixed"] or line["block_lines"] != 1:
        return False
    if text[-1] in ".,;:!?" or "@" in text or "," in text or _CAPTION.match(text):
        return False
    rest = _PREFIX.sub("", text)
    if not rest or not rest[0].isalpha() or not rest[0].isupper() or sum(c.isalpha() for c in rest) < 0.7 * len(rest):
        return False
    if line["size"] >= body * 1.1:
        return True
    return line["bold"] and line["size"] >= body * 0.95 and len(words) <= 8


ROW_GAP = 60.0  # points: cells of a table sit this close to each other; a figure's axis label across the page does not make a heading part of a row


def shares_row(line, lines):
    """Whether another line of the page sits on the same row as `line` (a table's cells, a figure's labels): a heading stands alone on its row, or has only its own
    section number beside it ("3.2" then "Results")."""
    x0, y0, x1, y1 = line["bbox"]
    height = max(y1 - y0, 1.0)
    for other in lines:
        if other is line:
            continue
        a0, b0, a1, b1 = other["bbox"]
        if min(y1, b1) - max(y0, b0) > 0.5 * height and (0 <= x0 - a1 < ROW_GAP or 0 <= a0 - x1 < ROW_GAP) and not re.fullmatch(r"(?:\d+(?:\.\d+)*\.?|[IVX]+\.|[A-Z]\.?)", other["text"].strip()):
            return True
    return False


def layout_headings(pages):
    """[(page_number, text, size, bold)] in reading order for every line that is set like a heading; [] without layout. The caller
    decides which of them count (not the title, not after the references)."""
    body = body_size(pages)
    if body is None:
        return []
    return [(page.page_number, line["text"], line["size"], line["bold"])
            for page in pages for line in getattr(page, "layout", None) or [] if _is_heading(line, body) and not shares_row(line, page.layout)]
