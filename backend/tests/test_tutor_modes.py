from backend.tutor import (
    TutorMode,
)


def test_tutor_modes():

    assert (
        TutorMode.INTUITION.value
        == "intuition"
    )

    assert (
        TutorMode.MATHEMATICS.value
        == "mathematics"
    )
