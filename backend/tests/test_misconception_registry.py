from backend.tutor import (
    TutorMode,
)

from backend.tutor.misconception_registry import (
    COMMON_MISCONCEPTIONS,
)


def test_misconception_mode():

    assert (

        TutorMode.MISCONCEPTION.value

        == "misconception"
    )

    assert (

        "Attention"

        in COMMON_MISCONCEPTIONS
    )
