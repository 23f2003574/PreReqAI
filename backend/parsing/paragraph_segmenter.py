import re

from backend.models import Paper, Paragraph


PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n")
_SPACES = re.compile(r"\s+")
_KEY = 60  # characters of a paragraph used to find its page
MAX_PARAGRAPH = 2500  # a paragraph longer than this without any layout to split it by is cut at a sentence end
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _by_layout(lines, starts):
    """The lines cut into paragraphs wherever a line is one the page's layout says opens a paragraph."""
    parts, current = [], []
    for line in lines:
        if current and " ".join(line.split())[:50] in starts:
            parts.append(current)
            current = []
        current.append(line)
    if current:
        parts.append(current)
    return ["\n".join(part).strip() for part in parts]


def _by_length(text):
    """A paragraph longer than MAX_PARAGRAPH, with no layout to split it by, cut at the sentence end nearest its middle until every piece fits."""
    if len(text) <= MAX_PARAGRAPH:
        return [text]
    ends = [match.end() for match in _SENTENCE_END.finditer(text)]
    if not ends:
        return [text]
    cut = min(ends, key=lambda position: abs(position - len(text) / 2))
    return _by_length(text[:cut].strip()) + _by_length(text[cut:].strip())


class ParagraphSegmenter:
    """
    Splits every detected paper section into
    individual logical paragraphs: at blank lines, then wherever the
    PDF's layout opens a paragraph (a block, an indented line after a
    short one), then, for what is still very long, at a sentence end.
    """

    def segment(
        self,
        paper: Paper,
    ) -> Paper:

        paragraph_counter = 1

        paper.paragraphs.clear()

        pages = [(page.page_number, _SPACES.sub(" ", page.text)) for page in getattr(paper, "pages", [])]
        starts = [set(getattr(page, "paragraph_starts", None) or []) for page in getattr(paper, "pages", [])]
        at = 0  # paragraphs follow the pages in order, so the search resumes at the page of the previous paragraph

        for section in paper.sections:

            chunks = []
            for chunk in PARAGRAPH_SPLIT_PATTERN.split(section.content.strip()):
                if not chunk.strip():
                    continue
                key = _SPACES.sub(" ", chunk.strip())[:_KEY]
                where = next((i for i in [*range(at, len(pages)), *range(at)] if key in pages[i][1]), None)
                known = set().union(*(starts[i] for i in (where, where + 1) if i is not None and i < len(starts))) if where is not None else set()
                pieces = _by_layout(chunk.strip().splitlines(), known) if known else [chunk.strip()]
                chunks.extend(piece for text in pieces for piece in _by_length(text) if piece)

            for cleaned in chunks:

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

        for page in getattr(paper, "pages", []):
            page.paragraph_starts = []  # layout is only needed to cut paragraphs; it is not kept in the paper or its saved session

        return paper
