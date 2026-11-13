# Typeset PDFs store "ffi", "fi", ... as single ligature glyphs and use typographic dashes inside
# compound names ("Q\u2011learning", "Actor\u2013Critic"); both must read as plain ASCII or concepts are missed.
_TEXT_FIXES = str.maketrans({
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2212": "-", "\u00ad": None,
    # typeset PDFs use no-break, thin and other fixed-width spaces ("1\u00a0Introduction"); the heading patterns match a plain space only
    "\u00a0": " ", "\u2002": " ", "\u2003": " ", "\u2009": " ", "\u202f": " ", "\u205f": " ", "\u3000": " ", "\u200b": None,
})


def clean_pdf_text(text: str) -> str:
    return text.translate(_TEXT_FIXES)


import re
from collections import Counter

# A running header, footer or page number repeats on many pages in the first or last lines of each page. Only lines that do both are removed;
# the same sentence repeated inside the body of a paper stays.
EDGE_LINES = 2  # the first and the last non-blank lines of a page are its header and footer zone
MIN_PAGES = 3  # fewer pages than this cannot show a repetition
MIN_SHARE = 0.4  # a line must open or close at least this share of the pages (alternating even/odd headers each appear on half)


def _repeat_key(line):
    """The line with its digits blanked, so "Page 3 of 10", "3" and "Smith et al. 12" repeat across pages."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", line.strip().lower()))


def _edge_positions(lines):
    """Indices of the first and last EDGE_LINES non-blank lines."""
    filled = [i for i, line in enumerate(lines) if line.strip()]
    return set(filled[:EDGE_LINES]) | set(filled[-EDGE_LINES:])


def drop_repeated_page_lines(texts):
    """(texts without running headers, footers and page numbers, number of lines removed per page). A line is removed only when it is
    in a page's header or footer zone and the same line (digits aside) is in the zone of at least MIN_SHARE of the pages, with at
    least MIN_PAGES pages; anything else, including a repeated line in the body, is left as extracted."""
    if len(texts) < MIN_PAGES:
        return list(texts), [0] * len(texts)
    split = [text.splitlines(keepends=True) for text in texts]
    zones = [_edge_positions(lines) for lines in split]
    seen = Counter(key for lines, zone in zip(split, zones) for key in {_repeat_key(lines[i]) for i in zone} if key)
    needed = max(MIN_PAGES, MIN_SHARE * len(texts))
    repeated = {key for key, pages in seen.items() if pages >= needed}
    cleaned, removed = [], []
    for lines, zone in zip(split, zones):
        drop = {i for i in zone if _repeat_key(lines[i]) in repeated}
        cleaned.append("".join(line for i, line in enumerate(lines) if i not in drop))
        removed.append(len(drop))
    return cleaned, removed
