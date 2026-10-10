import pymupdf as fitz  # PyMuPDF; "import fitz" prints a deprecation notice to stdout

from dataclasses import dataclass


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

        metadata = pdf.metadata or {}

        return DocumentMetadata(
            title=(metadata.get("title", "") or "").strip() or self._title_from_first_page(pdf) or "Unknown Title",
            author=metadata.get("author", "") or "Unknown Author",
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
                text = " ".join(span["text"].strip() for span in line["spans"] if span["text"].strip())
                if text:
                    lines.append((max(span["size"] for span in line["spans"]), text))
        head = lines[:5]
        return max(head, key=lambda item: item[0])[1][:200] if head else ""
