import pdfplumber

from dataclasses import dataclass, field

from .figure_extractor import ParsedPaperWithFigures


@dataclass
class PaperTable:
    table_id: int
    page_number: int
    rows: list[list[str]]


@dataclass
class ParsedPaperWithTables:
    parsed_paper: ParsedPaperWithFigures
    tables: list[PaperTable] = field(default_factory=list)


class TableExtractor:
    """
    Extracts tabular data from research papers.

    Each detected table is stored as a structured
    list of rows for downstream analysis.
    """

    def extract(
        self,
        pdf_path: str,
        parsed_paper: ParsedPaperWithFigures,
    ) -> ParsedPaperWithTables:

        tables = []

        table_counter = 1

        with pdfplumber.open(pdf_path) as pdf:

            for page_number, page in enumerate(pdf.pages, start=1):

                extracted_tables = page.extract_tables()

                for table in extracted_tables:

                    if not table:
                        continue

                    tables.append(
                        PaperTable(
                            table_id=table_counter,
                            page_number=page_number,
                            rows=table,
                        )
                    )

                    table_counter += 1

        return ParsedPaperWithTables(
            parsed_paper=parsed_paper,
            tables=tables,
        )
