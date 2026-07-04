import fitz

from dataclasses import dataclass, field

from .equation_extractor import ParsedPaperWithEquations


@dataclass
class PaperFigure:
    figure_id: int
    page_number: int
    image_index: int
    width: int
    height: int


@dataclass
class ParsedPaperWithFigures:
    parsed_paper: ParsedPaperWithEquations
    figures: list[PaperFigure] = field(default_factory=list)


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
        parsed_paper: ParsedPaperWithEquations,
    ) -> ParsedPaperWithFigures:

        document = fitz.open(pdf_path)

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

        document.close()

        return ParsedPaperWithFigures(
            parsed_paper=parsed_paper,
            figures=figures,
        )
