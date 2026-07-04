import fitz

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
        pdf = fitz.open(file_path)

        metadata = pdf.metadata or {}

        document_metadata = DocumentMetadata(
            title=metadata.get("title", "") or "Unknown Title",
            author=metadata.get("author", "") or "Unknown Author",
            subject=metadata.get("subject", ""),
            keywords=metadata.get("keywords", ""),
            creator=metadata.get("creator", ""),
            producer=metadata.get("producer", ""),
            page_count=len(pdf),
        )

        pdf.close()

        return document_metadata
