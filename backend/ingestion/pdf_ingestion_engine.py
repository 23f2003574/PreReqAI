import pymupdf as fitz  # PyMuPDF; "import fitz" prints a deprecation notice to stdout

from dataclasses import dataclass, field

from .document_metadata_extractor import DocumentMetadata


# Typeset PDFs store "ffi", "fi", ... as single ligature glyphs and use typographic dashes inside
# compound names ("Q\u2011learning", "Actor\u2013Critic"); both must read as plain ASCII or concepts are missed.
_TEXT_FIXES = str.maketrans({
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u00ad": None,
})


def clean_pdf_text(text: str) -> str:
    return text.translate(_TEXT_FIXES)


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
        from .document_metadata_extractor import DocumentMetadataExtractor

        # One open of the file serves both the metadata and the page text.
        with fitz.open(file_path) as pdf:

            metadata = DocumentMetadataExtractor().extract_from(pdf)

            pages = [
                RawPage(
                    page_number=page_number,
                    text=clean_pdf_text(page.get_text("text")),
                )
                for page_number, page in enumerate(pdf, start=1)
            ]

        return RawDocument(
            source_path=file_path,
            metadata=metadata,
            pages=pages,
        )
