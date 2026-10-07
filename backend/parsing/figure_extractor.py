import pymupdf as fitz  # PyMuPDF; "import fitz" prints a deprecation notice to stdout

from backend.models import Paper, PaperFigure


class FigureExtractor:
    """
    Extracts figure metadata from a research paper.

    Images are not exported yet.
    This stage simply identifies them and records
    where they exist inside the document.
    """

    def extract(
        self,
        pdf_path: str,
        paper: Paper,
    ) -> Paper:

        # closed even when an image fails to decode, like the other PDF readers
        with fitz.open(pdf_path) as document:

            figures = []

            figure_counter = 1

            for page_number, page in enumerate(document, start=1):

                for image_index, image in enumerate(page.get_images(full=True), start=1):

                    xref = image[0]

                    pixmap = fitz.Pixmap(document, xref)

                    figures.append(
                        PaperFigure(
                            figure_id=figure_counter,
                            page_number=page_number,
                            image_index=image_index,
                            width=pixmap.width,
                            height=pixmap.height,
                        )
                    )

                    figure_counter += 1

        paper.figures = figures

        return paper
