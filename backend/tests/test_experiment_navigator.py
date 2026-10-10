from backend.navigation import (
    ExperimentNavigator,
)

from backend.models import (
    Paper,
    Experiment,
)


def test_experiment_navigator_finds_matching_experiment():

    navigator = (
        ExperimentNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        experiments=[
            Experiment(
                experiment_id=1,
                title="Results",
                description="We evaluate on WMT 2014...",
                section="Results",
            ),
        ],
    )

    result = navigator.navigate(
        paper,
        "1",
    )

    assert result.target == "experiment"
    assert result.title == "Results"
    assert result.summary == "We evaluate on WMT 2014..."
    assert result.metadata["section"] == "Results"
    assert result.metadata["dataset"] is None
    assert result.metadata["metric"] is None


def test_experiment_navigator_raises_when_not_found():

    navigator = (
        ExperimentNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    try:
        navigator.navigate(
            paper,
            "9",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
