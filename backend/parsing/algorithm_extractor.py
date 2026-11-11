import re

from backend.models import Paper, PaperAlgorithm

from .reference_extractor import REFERENCES_TITLE


ALGORITHM_PATTERN = re.compile(
    r"^[ \t]*(Algorithm\s+\d+[:\s].*?)(?=\n\s*\n|\Z)",  # a caption starts its line: "in Algorithm 1 we ..." is a mention
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
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

            if REFERENCES_TITLE.match(section.title.strip()):
                continue

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
