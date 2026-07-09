from backend.navigation import (
    EquationNavigator,
)

from backend.models import (
    Paper,
    Equation,
)


def test_equation_navigator_finds_matching_equation():

    navigator = (
        EquationNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        equations=[
            Equation(
                equation_id=1,
                expression="Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V",
                section="Method",
            ),
            Equation(
                equation_id=2,
                expression="LayerNorm(x) = (x - mean) / std",
                section="Method",
            ),
        ],
    )

    result = navigator.navigate(
        paper,
        "2",
    )

    assert result.target == "equation"
    assert result.title == "Equation 2"
    assert result.summary == "LayerNorm(x) = (x - mean) / std"
    assert result.metadata["section"] == "Method"


def test_equation_navigator_raises_when_not_found():

    navigator = (
        EquationNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    try:
        navigator.navigate(
            paper,
            "7",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
