import re
import pymupdf as fitz  # PyMuPDF; "import fitz" prints a deprecation notice to stdout

from dataclasses import dataclass

from .text_cleaning import clean_pdf_text


@dataclass
class DocumentMetadata:
    title: str
    author: str
    subject: str
    keywords: str
    creator: str
    producer: str
    page_count: int


class DocumentMetadataExtractor:
    """
    Extracts metadata embedded inside a PDF document.
    """

    def extract(self, file_path: str) -> DocumentMetadata:

        with fitz.open(file_path) as pdf:

            return self.extract_from(pdf)

    def extract_from(self, pdf) -> DocumentMetadata:
        """The metadata of an already-open PDF, so a caller that has the
        document open does not parse the file a second time."""

        metadata = {key: clean_pdf_text(value) if isinstance(value, str) else value for key, value in (pdf.metadata or {}).items()}

        return DocumentMetadata(
            title=(metadata.get("title", "") or "").strip() or self._title_from_first_page(pdf) or "Unknown Title",
            author=(metadata.get("author", "") or "").strip() or self._author_from_first_page(pdf) or "Unknown Author",
            subject=metadata.get("subject", ""),
            keywords=metadata.get("keywords", ""),
            creator=metadata.get("creator", ""),
            producer=metadata.get("producer", ""),
            page_count=len(pdf),
        )

    @staticmethod
    def _title_from_first_page(pdf) -> str:
        """Most PDFs carry no title metadata: use the largest line among the first few lines of page one
        (the first of them when sizes tie), or "" when the page has no text."""
        if not len(pdf):
            return ""
        lines = []
        for block in pdf[0].get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                text = clean_pdf_text(" ".join(span["text"].strip() for span in line["spans"] if span["text"].strip()))
                if text:
                    lines.append((max(span["size"] for span in line["spans"]), text))
        head = lines[:5]
        if not head:
            return ""
        size, text = max(head, key=lambda item: item[0])
        if size - min(item[0] for item in head) < 1:  # one font size throughout: nothing marks a title, keep the first line
            return text[:200]
        # A long title wraps onto several lines of the same (largest) size: join the run that follows the first of them.
        start = next(index for index, item in enumerate(head) if item[0] == size)
        run = []
        for line_size, line_text in head[start:]:
            if abs(line_size - size) >= 0.5:
                break
            run.append(line_text)
        return " ".join(run)[:200]

    _NAME = re.compile(r"^[A-Z][\w.'\-]*(?: [A-Z][\w.'\-]*){1,3}$")
    _NOT_AUTHORS = re.compile(r"universit|institute|laborator|research|google|microsoft|department|school|abstract|@|\d|arxiv", re.I)

    @classmethod
    def _author_from_first_page(cls, pdf) -> str:
        """The author lines of page one when the metadata has none: the run of consecutive lines within the few after
        the title that are lists of person names (one author per line or several per line; affiliations, e-mail
        addresses and the abstract are skipped and end the run), or ""."""
        if not len(pdf):
            return ""
        lines = [line.strip() for line in clean_pdf_text(pdf[0].get_text()).splitlines() if line.strip()]
        authors = []
        for line in lines[1:12]:
            cleaned = re.sub(r"[*†‡§¶∗]", "", line).strip()
            names = [n.strip() for n in re.split(r",|\band\b|;", cleaned) if n.strip()]
            if names and not cls._NOT_AUTHORS.search(cleaned) and all(cls._NAME.match(n) for n in names):
                authors.extend(name for name in names if name not in authors)
            elif authors:
                break  # the author block ended (affiliation, e-mail, abstract)
        return ", ".join(authors)
