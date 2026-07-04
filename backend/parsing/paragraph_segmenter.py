import re

from backend.models import Paper, Paragraph


PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n")


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

        for section in paper.sections:

            chunks = PARAGRAPH_SPLIT_PATTERN.split(
                section.content.strip()
            )

            for chunk in chunks:

                cleaned = chunk.strip()

                if not cleaned:
                    continue

                paper.paragraphs.append(
                    Paragraph(
                        paragraph_id=paragraph_counter,
                        section_title=section.title,
                        content=cleaned,
                    )
                )

                paragraph_counter += 1

        return paper
