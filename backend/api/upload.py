from backend.ingestion import PDFIngestionEngine
from backend.parsing import ScientificSectionParser
from backend.parsing import EquationExtractor


def handle_pdf_upload(file_path: str):
    """
    Entry point used by future API endpoints.

    Returns a fully populated RawDocument.
    """

    engine = PDFIngestionEngine()

    document = engine.ingest(file_path)

    parser = ScientificSectionParser()
    parsed_paper = parser.parse(document)

    equation_extractor = EquationExtractor()

    return equation_extractor.extract(parsed_paper)
