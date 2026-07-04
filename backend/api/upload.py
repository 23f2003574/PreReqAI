from backend.ingestion import PDFIngestionEngine
from backend.parsing import ScientificSectionParser
from backend.parsing import EquationExtractor
from backend.parsing import FigureExtractor
from backend.parsing import TableExtractor


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

    parsed_with_equations = equation_extractor.extract(parsed_paper)

    figure_extractor = FigureExtractor()

    parsed_with_figures = figure_extractor.extract(
        file_path,
        parsed_with_equations,
    )

    table_extractor = TableExtractor()

    return table_extractor.extract(
        file_path,
        parsed_with_figures,
    )
