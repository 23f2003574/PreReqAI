import pytest

from backend.session import (
    normalize_research_tag_name,
)


def test_normalizes_research_tag_name():

    assert (

        normalize_research_tag_name(

            "  #Math Heavy  "
        )

        == "math-heavy"
    )


def test_rejects_empty_research_tag():

    with pytest.raises(

        ValueError,

        match="cannot be empty",
    ):

        normalize_research_tag_name(

            "###"
        )
