from backend.ingestion import PDFIngestionEngine


def handle_pdf_upload(file_path: str):
    """
    Entry point used by future API endpoints.

    Returns a fully populated RawDocument.
    """

    engine = PDFIngestionEngine()

    return engine.ingest(file_path)
