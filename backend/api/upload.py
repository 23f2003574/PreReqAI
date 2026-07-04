from backend.ingestion import PDFIngestionEngine
from backend.parsing import ScientificSectionParser
from backend.parsing import EquationExtractor
from backend.parsing import FigureExtractor
from backend.parsing import TableExtractor


def handle_pdf_upload(file_path: str):
    """
    Entry point used by future API endpoints.

    Returns a fully populated Paper.
    """

    engine = PDFIngestionEngine()

    document = engine.ingest(file_path)

    paper = ScientificSectionParser().parse(document)

    paper = EquationExtractor().extract(paper)

    paper = FigureExtractor().extract(
        file_path,
        paper,
    )

    paper = TableExtractor().extract(
        file_path,
        paper,
    )

    return paper
