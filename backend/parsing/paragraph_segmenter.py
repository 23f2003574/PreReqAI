import re

from backend.models import Paper, Paragraph


PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n")
_SPACES = re.compile(r"\s+")
_KEY = 60  # characters of a paragraph used to find its page


class ParagraphSegmenter:
    """
    Splits every detected paper section into
    individual logical paragraphs.
    """

    def segment(
        self,
        paper: Paper,
    ) -> Paper:

        paragraph_counter = 1

        paper.paragraphs.clear()

        pages = [(page.page_number, _SPACES.sub(" ", page.text)) for page in getattr(paper, "pages", [])]
        at = 0  # paragraphs follow the pages in order, so the search resumes at the page of the previous paragraph

        for section in paper.sections:

            chunks = PARAGRAPH_SPLIT_PATTERN.split(
                section.content.strip()
            )

            for chunk in chunks:

                cleaned = chunk.strip()

                if not cleaned:
                    continue

                key = _SPACES.sub(" ", cleaned)[:_KEY]
                found = next((i for i in [*range(at, len(pages)), *range(at)] if key in pages[i][1]), None)
                if found is not None:
                    at = found
                number = pages[found][0] if found is not None else getattr(section, "page_number", None)

                paper.paragraphs.append(
                    Paragraph(
                        paragraph_id=paragraph_counter,
                        section_title=section.title,
                        content=cleaned,
                        page_number=number,
                    )
                )

                paragraph_counter += 1

        return paper
