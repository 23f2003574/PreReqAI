import re

from backend.ingestion import RawDocument
from backend.models import Paper, PaperSection


SECTION_PATTERN = re.compile(
    r"^(Abstract|Introduction|Related Work|Background|Method|Methods|Methodology|Approach|Experiments|Experimental Setup|Results|Discussion|Conclusion|Conclusions|References|Appendix)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class ScientificSectionParser:
    """
    Detects high-level scientific paper sections
    using common research-paper headings.
    """

    def parse(self, document: RawDocument) -> Paper:

        text = document.full_text

        matches = list(SECTION_PATTERN.finditer(text))

        if not matches:
            sections = [
                PaperSection(
                    title="Full Paper",
                    content=text.strip(),
                )
            ]
        else:
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

        return Paper(
            source_path=document.source_path,
            metadata=document.metadata,
            pages=document.pages,
            sections=sections,
        )
