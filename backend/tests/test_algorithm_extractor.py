from backend.models import (
    Paper,
    PaperSection,
)

from backend.parsing import (
    AlgorithmExtractor,
)


def test_algorithm_detection():

    paper = Paper(
        source_path="sample.pdf",
        metadata=None,
    )

    paper.sections.append(

        PaperSection(

            title="Methods",

            content="""
Algorithm 1

Training Procedure

Initialize model
Train model
Evaluate model
"""
        )
    )

    paper = AlgorithmExtractor().extract(
        paper,
    )

    assert len(
        paper.algorithms
    ) == 1
