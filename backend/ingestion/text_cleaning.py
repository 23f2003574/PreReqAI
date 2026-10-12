# Typeset PDFs store "ffi", "fi", ... as single ligature glyphs and use typographic dashes inside
# compound names ("Q\u2011learning", "Actor\u2013Critic"); both must read as plain ASCII or concepts are missed.
_TEXT_FIXES = str.maketrans({
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u00ad": None,
})


def clean_pdf_text(text: str) -> str:
    return text.translate(_TEXT_FIXES)
