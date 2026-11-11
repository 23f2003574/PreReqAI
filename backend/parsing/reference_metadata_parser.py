import re


YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

SENTENCE_SPLIT_PATTERN = re.compile(r"\.\s+(?=[A-Z])")

# A full stop after a lone capital is an author's initial, not a sentence end, when a surname follows ("A. Vaswani, N. Shazeer. Title"):
# the next word is then followed by a comma, "and", a full stop or another initial. A title word ("N. Attention is all you need") is not.
_AUTHOR_INITIAL_BEFORE = re.compile(r"(?:^|[\s,])[A-Z]$")
_SURNAME_AFTER = re.compile(r"\s+[A-Z][\w'\u2019-]+(?:,|\s+and\b|\.|\s+[A-Z]\.)")
_INITIALS_ONLY = re.compile(r"^(?:[A-Z]\.?\s*)+$")


def _split_sentences(text: str) -> list[str]:
    segments, start = [], 0
    for match in SENTENCE_SPLIT_PATTERN.finditer(text):
        if _AUTHOR_INITIAL_BEFORE.search(text[start:match.start()]) and _SURNAME_AFTER.match(text, match.start() + 1):
            continue
        segments.append(text[start:match.start()])
        start = match.end()
    segments.append(text[start:])
    return segments


class ReferenceMetadataParser:
    """
    Best-effort heuristic parser that splits a raw
    bibliography line into authors/title/venue/year.

    Bibliography formatting varies widely, so fields
    that can't be confidently split are left empty
    rather than guessed.
    """

    def parse(
        self,
        raw_text: str,
    ) -> dict:

        segments = [

            segment.strip()

            for segment in _split_sentences(raw_text)

            if segment.strip()
        ]

        authors_segment = (
            segments[0] if segments else ""
        )

        title = (
            segments[1] if len(segments) > 1 else ""
        )

        venue = (
            " ".join(segments[2:])
            if len(segments) > 2
            else ""
        )

        year = self._extract_year(raw_text)

        return {

            "authors":
                self._split_authors(authors_segment),

            "title": title,

            "venue": venue,

            "year": year,
        }

    def _split_authors(
        self,
        segment: str,
    ) -> list[str]:

        segment = segment.replace(" and ", ", ")

        authors = []
        for author in (part.strip() for part in segment.split(",")):
            if not author:
                continue
            if authors and _INITIALS_ONLY.match(author):  # "Vaswani, A." lists the surname and its initials apart
                authors[-1] += f", {author}"
            else:
                authors.append(author)
        return authors

    def _extract_year(
        self,
        raw_text: str,
    ) -> int | None:

        matches = list(
            YEAR_PATTERN.finditer(raw_text)
        )

        if not matches:
            return None

        return int(matches[-1].group())
