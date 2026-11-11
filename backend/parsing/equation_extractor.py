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
    return words >= 3 or (words >= 2 and _SENTENCE_END.search(line.strip()) is not None)


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

        for section in paper.sections:

            if REFERENCES_TITLE.match(section.title.strip()):
                continue

            matches = DISPLAY_EQUATION_PATTERN.findall(
                section.content
            )

            for match in matches:

                if looks_like_prose(match):
                    continue

                equations.append(
                    Equation(
                        equation_id=equation_counter,
                        expression=match.strip(),
                        section=section.title,
                    )
                )

                equation_counter += 1

        paper.equations = equations

        return paper
