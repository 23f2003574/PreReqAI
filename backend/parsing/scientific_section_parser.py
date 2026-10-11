import re

from backend.ingestion import RawDocument
from backend.models import Paper, PaperSection


_KNOWN = (
    r"(?:\d+(?:\.\d+)*\.?\s+)?(?:Abstract|Introduction|Related Work|Background|Method|Methods|Methodology|Approach|"
    r"Experiments|Experimental Setup|Results|Discussion|Conclusion|Conclusions|References|Appendix)"
)
# A numbered, title-cased line such as "3.2 Scaled Dot-Product Attention": at most 8 words, no digits or sentence punctuation.
_WORD = r"(?:[A-Z][A-Za-z\-]*|of|and|the|for|in|to|with|a|an|on|via|by|from|as)"
_NUMBERED = rf"\d+(?:\.\d+)*\.?[ \t]+[A-Z][A-Za-z\-]*(?:[ \t]+{_WORD}){{0,7}}"

SECTION_PATTERN = re.compile(rf"^(?:(?i:{_KNOWN})|{_NUMBERED})[ \t]*$", re.MULTILINE)


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

            front = text[:matches[0].start()].strip()

            if front:  # title and abstract text before the first recognised heading

                sections.append(PaperSection(title="Front Matter", content=front))

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
