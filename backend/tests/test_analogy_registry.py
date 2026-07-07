from backend.tutor import (
    TutorMode,
)

from backend.tutor.analogy_registry import (
    COMMON_ANALOGIES,
)


def test_analogy_mode():

    assert (

        TutorMode.ANALOGY.value

        == "analogy"
    )

    assert (

        "Transformer"

        in COMMON_ANALOGIES
    )
