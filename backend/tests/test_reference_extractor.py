from backend.parsing import ReferenceExtractor

from backend.models import (
    Paper,
    PaperSection,
)


def test_reference_extractor_joins_multiline_entries():

    extractor = ReferenceExtractor()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        sections=[
            PaperSection(
                title="References",
                content=(
                    "[1] Jimmy Lei Ba, Jamie Ryan Kiros, and Geoffrey E Hinton. Layer normalization. arXiv preprint\n"
                    "arXiv:1607.06450, 2016.\n"
                    "[2] Dzmitry Bahdanau, Kyunghyun Cho, and Yoshua Bengio. Neural machine translation by jointly\n"
                    "learning to align and translate. CoRR, abs/1409.0473, 2014."
                ),
            ),
        ],
    )

    result = extractor.extract(paper)

    assert len(result.references) == 2

    assert result.references[0].reference_number == 1
    assert (
        result.references[0].raw_text
        == "Jimmy Lei Ba, Jamie Ryan Kiros, and Geoffrey E Hinton. Layer normalization. arXiv preprint arXiv:1607.06450, 2016."
    )

    assert result.references[1].reference_number == 2
    assert "CoRR, abs/1409.0473, 2014." in result.references[1].raw_text
