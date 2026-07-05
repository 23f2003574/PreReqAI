import re

from backend.models import Paper, PaperAlgorithm


ALGORITHM_PATTERN = re.compile(
    r"(Algorithm\s+\d+[:\s].*?)(?=\n\s*\n|\Z)",
    re.IGNORECASE | re.DOTALL,
)


class AlgorithmExtractor:
    """
    Extracts algorithm blocks from scientific
    papers and stores them as structured
    objects.
    """

    def extract(
        self,
        paper: Paper,
    ) -> Paper:

        paper.algorithms.clear()

        algorithm_counter = 1

        for section in paper.sections:

            matches = ALGORITHM_PATTERN.findall(
                section.content
            )

            for match in matches:

                first_line = match.splitlines()[0]

                paper.algorithms.append(

                    PaperAlgorithm(
                        algorithm_id=algorithm_counter,
                        title=first_line.strip(),
                        content=match.strip(),
                        section=section.title,
                    )
                )

                algorithm_counter += 1

        return paper
