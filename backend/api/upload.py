from backend.ingestion import PDFIngestionEngine
from backend.parsing import ScientificSectionParser


def handle_pdf_upload(file_path: str):
    """
    Entry point used by future API endpoints.

    Returns a fully populated RawDocument.
    """

    engine = PDFIngestionEngine()

    document = engine.ingest(file_path)

    parser = ScientificSectionParser()

    return parser.parse(document)
