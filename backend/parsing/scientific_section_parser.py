import re

from dataclasses import dataclass, field

from backend.ingestion import RawDocument


SECTION_PATTERN = re.compile(
    r"^(Abstract|Introduction|Related Work|Background|Method|Methods|Methodology|Approach|Experiments|Experimental Setup|Results|Discussion|Conclusion|Conclusions|References|Appendix)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class PaperSection:
    title: str
    content: str


@dataclass
class ParsedPaper:
    document: RawDocument
    sections: list[PaperSection] = field(default_factory=list)


class ScientificSectionParser:
    """
    Detects high-level scientific paper sections
    using common research-paper headings.
    """

    def parse(self, document: RawDocument) -> ParsedPaper:

        text = document.full_text

        matches = list(SECTION_PATTERN.finditer(text))

        if not matches:
            return ParsedPaper(
                document=document,
                sections=[
                    PaperSection(
                        title="Full Paper",
                        content=text.strip(),
                    )
                ],
            )

        sections = []

        for index, match in enumerate(matches):

            start = match.end()

            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            )

            sections.append(
                PaperSection(
                    title=match.group().strip(),
                    content=text[start:end].strip(),
                )
            )

        return ParsedPaper(
            document=document,
            sections=sections,
        )
