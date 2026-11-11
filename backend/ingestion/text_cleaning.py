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
