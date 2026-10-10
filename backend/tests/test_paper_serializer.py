from backend.serialization import (
    PaperSerializer,
)

from backend.models import (
    Paper,
)


def test_serializer_returns_dictionary():

    paper = Paper(
        source_path="sample.pdf",
        metadata=None,
    )

    serializer = PaperSerializer()

    result = serializer.serialize(paper)

    assert isinstance(result, dict)
