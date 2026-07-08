from backend.workflows import (
    LearningIntent,
    LearningIntentDetector,
)


def test_intent_detection():

    detector = (
        LearningIntentDetector()
    )

    assert (

        detector.detect(

            "Explain Attention"

        )

        == LearningIntent.EXPLAIN
    )

    assert (

        detector.detect(

            "Show PyTorch implementation"

        )

        == LearningIntent.IMPLEMENT
    )

    assert (

        detector.detect(

            "Compare CNN and Transformer"

        )

        == LearningIntent.COMPARE
    )
