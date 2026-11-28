import re

from backend.models import Paper, Equation

from .reference_extractor import REFERENCES_TITLE


DISPLAY_EQUATION_PATTERN = re.compile(
    r"^\s*.+?=\s*.+$",
    re.MULTILINE,
)

# Words that appear inside formulas ("exp", "sum", "softmax"...) and so say nothing about a line being a sentence.
_MATH_WORDS = frozenset({
    "exp", "log", "ln", "sum", "prod", "max", "min", "argmax", "argmin", "softmax", "sigmoid", "relu", "tanh", "sin", "cos", "tan",
    "det", "var", "cov", "std", "mean", "norm", "sign", "abs", "dim", "tr", "diag", "inf", "sup", "lim", "mod", "loss", "for",
    "all", "and", "otherwise", "else", "over", "subject", "such", "that", "where",
})
# Two-letter words are too short to count as English unless they are one of these common function words.
_SHORT_PROSE_WORDS = frozenset({"is", "of", "in", "to", "on", "as", "at", "by", "we", "an", "or", "if", "it", "be", "so", "do"})
_WORD = re.compile(r"[A-Za-z]+")
_SENTENCE_END = re.compile(r"[A-Za-z0-9%)]\.$")


# Arithmetic inside a sentence ("so he travels for 3 * 6 = 18 miles. The ...", "... = $50.00. The answer is ...") is a worked example in the text, not a display equation: it
# continues into a sentence, carries a unit, a currency amount, a percentage or quotation marks, or opens with ordinary words.
_SENTENCE_BOUNDARY = re.compile(r"[.!?]\s+[A-Z][a-z]")
_UNIT_AFTER_RESULT = re.compile(r"=\s*[$\u20ac\u00a3]?\d+(?:[.,]\d+)*\s*(?:%|[a-z]{3,}\b)")
_CURRENCY = re.compile(r"[$\u20ac\u00a3]\d")  # "$x$" is TeX; "$50.00" is money
_OPENS_WITH_WORDS = re.compile(r"^[a-z]{2,}\s+[a-z]{2,}\b")


# Things a PDF text layer returns that are not display equations: a chart or table label ("N=16", "DPO (temp = 1.0)"), a line of program code (snake_case names, return/while, "x = y[i]"), and a prose
# fragment that happens to contain "=" (several lower-case ordinary words and a sentence end).
_LABEL_NUMBER = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,3}\s*=\s*\d+(?:\.\d+)?$")
_LEGEND = re.compile(r"^[A-Za-z][\w\- ]*\(\s*\w+\s*=\s*[\d.]+\s*\)$")
_CODE = re.compile(r"\b[a-z]+_[a-z_0-9]+\b|\b(?:return|while|for|def|import|lambda)\b|\b(?:F|torch|np)\.[a-z]|;\s*\w+\s*[-+]?=|^\w+\s*\+?=\s*\w+\[")


def looks_like_non_equation(line: str) -> bool:
    """A chart or table label, a legend, a line of code or a prose fragment: reported by the text layer next to equations but not itself one."""
    text = " ".join(line.split())
    return bool(_LABEL_NUMBER.match(text) or _LEGEND.match(text) or _CODE.search(text) or (_word_count(text) >= 3 and _SENTENCE_END.search(text.split("=")[-1].strip()) and not any(c in text for c in "∑∫∇∂∼")))


def is_prose_arithmetic(line: str) -> bool:
    text = line.strip()
    return bool(_SENTENCE_BOUNDARY.search(text) or _UNIT_AFTER_RESULT.search(text) or _CURRENCY.search(text) or "%" in text or "\u201c" in text or "\u201d" in text
                or (_OPENS_WITH_WORDS.match(text) and _word_count(text) >= 2))


def _word_count(line: str) -> int:
    return sum(1 for token in line.split() if token.strip(".,;:").isalpha() and token.islower() and token.strip(".,;:") not in _MATH_WORDS and len(token.strip(".,;:")) >= 2)


def looks_like_prose(line: str) -> bool:
    """Whether a line holding "=" is a sentence rather than a formula ("where x = 5 is the number of users.").

    Conservative on purpose: a line is prose only when it has three or more plain lowercase English words (two when it also ends
    like a sentence). A token is a word only if it is purely alphabetic and lowercase, so symbols ("lr", "W_k"), function calls
    ("softmax(z)") and capitalised names are never counted, and common formula words ("exp", "sum", "where"...) are ignored."""
    words = 0
    for token in line.split():
        token = token.strip(".,;:")
        if not _WORD.fullmatch(token) or not token.islower() or token in _MATH_WORDS:
            continue
        if len(token) >= 3 or token in _SHORT_PROSE_WORDS:
            words += 1
    return words >= 3 or (words >= 2 and _SENTENCE_END.search(line.strip()) is not None) or is_prose_arithmetic(line)


_CONTINUATION = re.compile(r"^(?:where|with|and|such that|if|for|otherwise)\b", re.IGNORECASE)


class EquationExtractor:
    """
    Extracts display-style mathematical equations
    from each detected paper section.

    Initial implementation intentionally targets
    common research-paper equation layouts.
    Sentences that merely contain "=" and the bibliography are not equations.
    """

    def extract(self, paper: Paper) -> Paper:

        equations = []

        equation_counter = 1

        titles = {section.title for section in paper.sections}
        skipped = {section.title for section in paper.sections if REFERENCES_TITLE.match(section.title.strip())}
        pieces = {" ".join(text.split()) for page in getattr(paper, "pages", []) for group in (getattr(page, "equation_groups", None) or []) for text in group["fragments"]}

        for page in getattr(paper, "pages", []):  # display equations rebuilt from the layout, in page order
            for group in getattr(page, "equation_groups", None) or []:
                anchor = group["fragments"][0] if group["fragments"] else ""
                section = _section_of(paper, page.page_number, anchor)
                if section is None or section in skipped or looks_like_non_equation(group["text"]):
                    continue
                if equations and not group["tag"] and _CONTINUATION.match(group["text"]) and equations[-1].page_number == page.page_number and equations[-1].section == section:
                    equations[-1].expression += " " + group["text"]  # "where Z(x) = ..." defines a symbol of the display above it: part of that equation, not another one
                    continue
                equations.append(Equation(equation_id=equation_counter, expression=group["text"], section=section, page_number=page.page_number, tag=group["tag"], anchor=anchor))
                equation_counter += 1
            page.equation_groups = []  # the layout is only needed to rebuild the equations; it is not kept in the paper or its saved session

        for section in paper.sections:

            if section.title in skipped:
                continue

            matches = DISPLAY_EQUATION_PATTERN.findall(
                section.content
            )

            for match in matches:

                if looks_like_prose(match) or looks_like_non_equation(match) or any(" ".join(line.split()) in pieces for line in match.splitlines()):  # a piece of a display already rebuilt above
                    continue

                equations.append(
                    Equation(
                        equation_id=equation_counter,
                        expression=match.strip(),
                        section=section.title,
                        page_number=getattr(section, "page_number", None),
                    )
                )

                equation_counter += 1

        paper.equations = equations

        return paper


def _section_of(paper: Paper, page_number, anchor: str):
    """The section an equation on `page_number` belongs to: the one whose text holds its first piece, else the last section that begins on or before that page."""
    key = " ".join(anchor.split())
    holding = [section.title for section in paper.sections
               if key and key in " ".join(section.content.split()) and (getattr(section, "page_number", None) is None or section.page_number <= page_number)]
    if holding:
        return holding[-1]  # the same expression may be quoted in an earlier section: the nearest one before the page is the one it is displayed in
    earlier = [section for section in paper.sections if section.page_number is not None and section.page_number <= page_number]
    return earlier[-1].title if earlier else None
