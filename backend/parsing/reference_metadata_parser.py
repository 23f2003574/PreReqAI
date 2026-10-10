import re


YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

SENTENCE_SPLIT_PATTERN = re.compile(r"\.\s+(?=[A-Z])")


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

            for segment in SENTENCE_SPLIT_PATTERN.split(
                raw_text
            )

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

        return [

            author.strip()

            for author in segment.split(",")

            if author.strip()
        ]

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
