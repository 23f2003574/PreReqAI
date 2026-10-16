import pdfplumber
import pymupdf

from backend.models import Paper, PaperTable


class TableExtractor:
    """
    Extracts tabular data from research papers.

    Each detected table is stored as a structured
    list of rows for downstream analysis.
    """

    def extract(
        self,
        pdf_path: str,
        paper: Paper,
    ) -> Paper:

        tables = []

        drawn_pages = self._pages_with_vector_graphics(pdf_path)

        table_counter = 1

        # No page draws anything: nothing can be found, so the file is not opened a third time (which
        # parses every page object). Otherwise pdfplumber is told which pages it will be asked about.
        if drawn_pages is not None and not drawn_pages:
            paper.tables = tables
            return paper

        with pdfplumber.open(pdf_path, pages=sorted(drawn_pages) if drawn_pages else None) as pdf:

            for page in pdf.pages:

                page_number = page.page_number

                # pdfplumber's default (ruled-line) detection finds nothing on a page with no
                # lines or rectangles, but loading that page's objects is by far the slowest
                # stage of an analysis; PyMuPDF answers the same question almost instantly.
                if drawn_pages is not None and page_number not in drawn_pages:
                    continue

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

        paper.tables = tables

        return paper

    @staticmethod
    def _pages_with_vector_graphics(pdf_path):
        """1-based numbers of pages that draw any line, rectangle or curve, or None
        when that cannot be determined (every page is then examined)."""

        try:

            with pymupdf.open(pdf_path) as document:

                return {
                    number
                    for number, page in enumerate(document, start=1)
                    if page.get_drawings()
                }

        except Exception:

            return None
