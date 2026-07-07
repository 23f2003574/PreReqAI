from backend.tutor import (
    RuleBasedTutor,
)

from backend.session import (
    RetrievedContext,
)


def test_rule_based_tutor():

    context = RetrievedContext(

        concepts=["Attention"],

        sections=["Method"],

        equations=[],
    )

    response = (
        RuleBasedTutor()
        .answer(

            None,

            context,

            "Explain Attention",
        )
    )

    assert response.confidence == 0.0

    assert (
        "Attention"

        in response.supporting_concepts
    )
