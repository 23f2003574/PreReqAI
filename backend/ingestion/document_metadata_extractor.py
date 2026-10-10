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
            title=metadata.get("title", "") or "Unknown Title",
            author=metadata.get("author", "") or "Unknown Author",
            subject=metadata.get("subject", ""),
            keywords=metadata.get("keywords", ""),
            creator=metadata.get("creator", ""),
            producer=metadata.get("producer", ""),
            page_count=len(pdf),
        )
