import fitz  # PyMuPDF

from dataclasses import dataclass, field

from .document_metadata_extractor import DocumentMetadata


@dataclass
class RawPage:
    page_number: int
    text: str


@dataclass
class RawDocument:
    source_path: str
    metadata: DocumentMetadata
    pages: list[RawPage] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(page.text for page in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)


class PDFIngestionEngine:
    """
    Reads a research paper PDF and converts it into
    PreReqAI's raw internal document representation.
    """

    def ingest(self, file_path: str) -> RawDocument:
        pdf = fitz.open(file_path)

        from .document_metadata_extractor import DocumentMetadataExtractor

        metadata = DocumentMetadataExtractor().extract(file_path)

        pages = []

        for page_number, page in enumerate(pdf, start=1):
            pages.append(
                RawPage(
                    page_number=page_number,
                    text=page.get_text("text"),
                )
            )

        pdf.close()

        return RawDocument(
            source_path=file_path,
            metadata=metadata,
            pages=pages,
        )
